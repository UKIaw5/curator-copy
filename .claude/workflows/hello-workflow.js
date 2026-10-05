export const meta = {
  name: 'hello-workflow',
  description: 'Workflowの最小サンプル(ハンズオン学習用)',
  phases: [{ title: 'Greet' }],
}

phase('Greet')
const result = await agent('「こんにちは、Workflowのテストです」と一言だけ日本語で返して。他には何も書かないで。')
log(result)
return result
