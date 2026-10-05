export const meta = {
  name: 'audit-note-drafts',
  description: 'note.com下書き記事を公開前に監査する(ハルシネーション/日本語/フォーマット/リンク事故チェック)',
  phases: [{ title: 'Audit' }],
}

// args: [{ id, generated_path, raw_path, idx }, ...]
// 💡 元データ・生成記事の全文をargsに積むとオーケストレーター側(このJS)の
// コンテキストが膨らむため、ファイルパスと位置情報だけを渡し、
// 実際のファイル読み込み・分割はサブエージェント自身にやらせる設計にする
// (agent()で呼ばれる側はRead/Bashツールを持つので、ファイルアクセス可能)。

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    passed: { type: 'boolean', description: '公開して問題ないか' },
    hallucination_found: { type: 'boolean', description: '元データにない具体的事実・数値・事例を、断定的な事実として生成記事が書いているか(ヘッジされた推測は対象外)' },
    japanese_quality_ok: { type: 'boolean', description: '日本語として自然か(英語混入・拒否文の残骸がないか)' },
    format_ok: { type: 'boolean', description: 'Markdown見出しやタイトル行が崩れていないか' },
    reasons: { type: 'array', items: { type: 'string' }, description: '判定理由(日本語、具体的に)' },
  },
  required: ['passed', 'hallucination_found', 'japanese_quality_ok', 'format_ok', 'reasons'],
}

function buildPrompt(item) {
  return `あなたはnote.com記事の公開前監査担当です。

まず以下を実行してください:
1. ${item.generated_path} を読む(これが「生成記事」)
2. ${item.raw_path} を読み、その中身を区切りトークン"<<<CURATOR_ITEM_BOUNDARY>>>"で分割する(このトークンが見つからない場合のみ、"---"で分割する旧形式として扱う)。分割した配列の${item.idx}番目(0始まり)の要素が「元データ」
3. 他のファイルは読まないこと。

# このプロジェクト固有の仕様(誤検知しないこと)
以下は意図的な仕様であり、問題ではない。これらだけを理由にpassed=falseにしないこと:
- 本文中の"<!-- PAYWALL -->"というHTMLコメントは、有料/無料エリアの境界マーカーであり、公開処理の時点で取り除かれる。生成記事ファイルに残っているのは正常。
- "なぜなら——"のように、パラグラフが文の途中で意図的に切れている箇所(特に<!-- PAYWALL -->の直前)は、続きを読ませるための「ペイウォール・クリフハンガー」という設計上のフック。未完成な文章ではない。
- 記事末尾の"#タグ名 #タグ名"のようなハッシュタグの並びは、note.com投稿の仕様として必須。
- 「■ 筆者の視点」セクションは、意図的に**断定を避けた推測・類推・問いかけ**を書く欄として設計されている(「〜かもしれない」「〜という問いが残る」「似た発想は〇〇にも見られる」等のヘッジ表現を使う)。このセクションが元データにない解釈・類推・疑問を述べているのは仕様であり、それ自体はハルシネーションではない。

# 本当にチェックすべき観点
1. ハルシネーション: 生成記事が、元データから読み取れない具体的な技術詳細・数値・固有名詞・事例を、**断定的な事実として**書いていないか(「〜である」「〜を導入している」等)。ヘッジされた推測表現(「〜かもしれない」「〜とも考えられる」「〜という問いが残る」)を使っている箇所は、たとえ元データにない解釈でもhallucination_foundの対象にしないこと。見分け方: 断定か推測かは文末の言い切り方で判断する。元データが極端に短い(タイトル+URLのみ等)のに、本文セクション(■筆者の視点以外)で具体的な技術詳細を断定的に書いている場合は、ほぼ確実にhallucination_foundをtrueにすること。
2. 日本語品質: 英語がそのまま混入していないか、「申し訳ございません」等のモデルの拒否文がそのまま本文に残っていないか、韓国語(ハングル)や中国語の単語・文字が混入していないか(日本語の漢字と誤認しないよう注意。例: "扩散"は中国語の簡体字で、正しい日本語は"拡散")。
3. フォーマット: 見出し(■等)やタイトル行が崩れていないか、Markdownの残骸(バッククォート・[](  )等)が残っていないか、同じ見出し行が記事内に2回以上出現していないか、コード例の中のコメント(#で始まる行)が誤って見出し記号(■)に変換されて壊れていないか。
4. 上記のいずれかに問題があればpassedはfalseにすること。`
}

phase('Audit')
// 💡 argsがJSON文字列として渡ってくる場合があるため両対応する
// (実例で確認: 配列として渡しても文字列化されて届くケースがあった)
const items = typeof args === 'string' ? JSON.parse(args) : args
const results = await parallel(
  items.map((item, i) => () =>
    agent(buildPrompt(item), {
      label: `audit:${item.id}`,
      model: 'haiku',
      schema: VERDICT_SCHEMA,
    }).then((verdict) => ({ id: item.id, verdict }))
  )
)

for (const r of results) {
  if (!r) continue
  log(`${r.id}: passed=${r.verdict.passed} hallucination=${r.verdict.hallucination_found}`)
}

return results
