// Dependências de geração, sem impacto na execução da API.
const fs = require('node:fs');
const path = require('node:path');

async function main() {
  const { instance } = require('../tmp/diagramas/node_modules/@viz-js/viz');
  const sharp = require(process.env.SHARP_MODULE || '../tmp/diagramas/node_modules/sharp');
  const viz = await instance();
  const pasta = path.resolve(__dirname, '../docs/diagramas');
  for (const nome of fs.readdirSync(pasta).filter(nome => nome.endsWith('.dot'))) {
    const svg = viz.renderString(fs.readFileSync(path.join(pasta, nome), 'utf8'), { format: 'svg' });
    await sharp(Buffer.from(svg), { density: 160 }).png().toFile(path.join(pasta, nome.replace('.dot', '.png')));
    console.log(nome);
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
