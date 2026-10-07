export const meta = {
  name: 'refine-x-posts',
  description: 'Stage1の英語詳細要約から、日本語のXポスト本文をClaudeが直接生成する(Gemma refinerの代替)',
  phases: [{ title: 'Refine' }],
}

// args: [{ idx, raw_path }, ...]
// 💡 audit-note-drafts.jsと同じ理由で、生データの全文をargsに積まず
// ファイルパスと位置情報だけを渡す。実際の読み込み・分割・URL抽出は
// サブエージェント自身にやらせる(Read/Bashツールを持つため可能)。

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    body_text: { type: 'string', description: 'XポストのURLを含まない本文(日本語)' },
    url: { type: 'string', description: '元データ中の "Source:" 行等から抽出したURL。見つからなければ空文字' },
  },
  required: ['body_text', 'url'],
}

function buildPrompt(item) {
  return `あなたはXのTech系投稿を書くシャープで信頼できる日本語ライターです。

まず以下を実行してください:
1. ${item.raw_path} を読む。
2. 中身を区切りトークン"<<<CURATOR_ITEM_BOUNDARY>>>"で分割する(このトークンが見つからない場合のみ、"---"で分割する旧形式として扱う)。分割した配列の${item.idx}番目(0始まり)の要素が「元データ」(英語の技術要約)。
3. 元データ内に"Source: https://..."のような行があれば、そのURLを抽出する(無ければurlは空文字)。
4. 他のファイルは読まないこと。

元データを元に、以下のルールに従って日本語のXポスト本文(URLは含めない)を書いてください:

1. 書き出しは、最もインパクトのある具体的な事実(数値・結果)から入り、読み手の注意を引いてください。製品名・論文名・ライブラリ名は、その直後の自然な流れの中で明かしてください(例: 「Rank-8のLoRAを当てるだけで精度が15.5%から99%に跳ね上がる。その手法の名はEarly-Layer LoRA。」のように、事実→名前の順)。
2. 「神」「ヤバい」「エグい」のような中身のない誇張表現だけに頼らず、元データの中にある**具体的な事実を1つ以上**(数値、手法名、ベンチマーク結果、仕組みなど)を必ず盛り込んでください。元データに無い具体的な数値・事例を創作しないこと。
3. 文字数に余裕がある場合のみ、この情報が読み手(個人開発者・エンジニア)にとってどう役立つかを一言添えてください。文字数を超過するくらいなら、この一言は省略してください。
4. 絵文字は任意です。使う場合は1つだけ、文末付近に自然に置いてください(句読点の直後は避ける)。
5. だ・である調(タメ語)で書き、です・ます調は使わないこと。
6. 日本語のみで書くこと。英語・韓国語・簡体字中国語の単語や文字を混入させないこと。
7. 本文の文字数は、URLがある場合は実効文字数(本文の文字数+25)が60〜135文字に収まるように、無い場合は本文の文字数が60〜135文字に収まるようにしてください。目安は80〜110文字です(最優先事項、超過厳禁)。
8. 出力はbody_text(本文のみ、URLは含めない)とurl(抽出したURL、無ければ空文字)の2つだけ。`
}

phase('Refine')
const items = typeof args === 'string' ? JSON.parse(args) : args
const results = await parallel(
  items.map((item, i) => () =>
    agent(buildPrompt(item), {
      label: `refine:${item.idx}`,
      model: 'haiku',
      schema: VERDICT_SCHEMA,
    }).then((result) => ({ idx: item.idx, body_text: result.body_text, url: result.url }))
  )
)

for (const r of results) {
  if (!r) continue
  const effLen = (r.body_text || '').length + (r.url ? 25 : 0)
  log(`idx ${r.idx}: body=${(r.body_text || '').length}chars effective=${effLen}chars`)
}

return results
