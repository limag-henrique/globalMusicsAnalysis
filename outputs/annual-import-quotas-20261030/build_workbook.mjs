import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const root = 'D:/PromiscuidadeMusical';
const input = path.join(root, 'data/derived/research_quality/import-quotas-20261030');
const output = path.join(root, 'outputs/annual-import-quotas-20261030');
const countries = JSON.parse(await fs.readFile(path.join(input, 'countries.json'), 'utf8'));
const cells = JSON.parse(await fs.readFile(path.join(input, 'cells.json'), 'utf8'));
const summary = JSON.parse(await fs.readFile(path.join(input, 'allocation_summary.json'), 'utf8'));
const wb = Workbook.create();
const overview = wb.worksheets.add('Resumo');
const countrySheet = wb.worksheets.add('Cotas por país');
const yearSheet = wb.worksheets.add('País e ano');
const dark = '#263B53';

function setup(sheet, range) {
  sheet.showGridLines = false;
  sheet.getRange(range).format.font = { name: 'Arial', size: 10, color: '#202B35' };
  sheet.getRange(range).format.rowHeight = 22;
  sheet.getRange(range).format.verticalAlignment = 'center';
}
function header(sheet, range) {
  sheet.getRange(range).format = { fill: dark, font: { name: 'Arial', size: 10, color: '#FFFFFF', bold: true }, wrapText: true, horizontalAlignment: 'center', verticalAlignment: 'center', rowHeight: 34 };
}
setup(overview, 'A1:D30');
overview.getRange('A2').values = [['Cotas de importação de músicas']];
overview.getRange('A2').format.font = { name: 'Arial', size: 14, bold: true };
overview.getRange('A4:B4').values = [['Parâmetro', 'Valor']];
header(overview, 'A4:B4');
const info = [
 ['Orçamento total (US$)', summary.total_budget_usd],
 ['Meta global de identidades', summary.target_unique_main],
 ['Identidades observadas no plano principal', summary.unique_observed_candidates_main],
 ['Identidades com calendário elegível', summary.unique_calendar_eligible_candidates],
 ['Custo unitário estimado pelo pesquisador (US$)', summary.unit_cost_assumption_usd],
 ['Custo estimado do plano observado (US$)', null],
 ['Saldo após o plano observado (US$)', null],
 ['Coeficiente principal calibrado', summary.main_coefficient],
 ['Coeficiente de expansão calibrado', summary.expansion_coefficient],
 ['Base por país e ano', summary.baseline_per_country_year],
 ['Teto por país e ano', summary.cap_per_country_year],
 ['Passo de arredondamento', summary.rounding_step],
 ['Identidades observadas na expansão', summary.unique_observed_candidates_expansion],
 ['Reserva para identidades ainda desconhecidas', summary.reserve_main_unknown_candidates],
 ['Custo estimado da expansão observada (US$)', null],
 ['Custo da meta global principal (US$)', null],
 ['Data de corte das capturas locais', summary.local_capture_cutoff],
 ['Células com calendário elegível', summary.calendar_eligible_cells],
 ['Células anuais completas', summary.calendar_eligible_cells - summary.partial_2026_eligible_cells],
 ['Células parciais de 2026 com janela completa', summary.partial_2026_eligible_cells],
 ['Células sem dados locais', summary.cells_without_local_data],
 ['Células com calendário incompleto', summary.incomplete_calendar_cells],
 ['Janela candidata de pesquisa', '2017–2026'],
 ['Coeficiente da sensibilidade só população', summary.population_only_coefficient],
];
overview.getRange(`A5:B${4+info.length}`).values = info;
overview.getRange('B10').formulas = [['=B7*B9']];
overview.getRange('B11').formulas = [['=B5-B10']];
overview.getRange('B19').formulas = [['=B17*B9']];
overview.getRange('B20').formulas = [['=B6*B9']];
overview.getRange('B5:B28').setNumberFormat('#,##0');
for (const cell of ['B5','B10','B11','B19','B20']) overview.getRange(cell).setNumberFormat('"US$ "#,##0.00');
overview.getRange('B9').setNumberFormat('"US$ "0.000');
for (const cell of ['B12','B13','B28']) overview.getRange(cell).setNumberFormat('0.000000');
overview.getRange('A1:A30').format.columnWidth = 58;
overview.getRange('B1:B30').format.columnWidth = 21;
overview.getRange('C1:C30').format.columnWidth = 3;
overview.getRange('D1:D30').format.columnWidth = 110;
overview.getRange('D5:D13').values = [
 ['Cálculo local em 30/10/2026. Não executa importação nem chamadas pagas.'],
 ['A meta global conta identidades candidatas; a deduplicação de letras será posterior.'],
 ['Inclui dados incompletos apenas no planejamento conservador de custo.'],
 ['Calendário elegível ainda exige auditoria da extração e da identidade.'],
 ['US$0,001 por música é hipótese do pesquisador, não preço verificado.'],
 ['Anos ausentes exigem coleta e nova contagem antes de qualquer envio pago.'],
 ['Diversidade étnica histórica: Alesina et al. (2003), medições de 1981–2001.'],
 ['2026 é uma janela parcial até 15/10/2026; não equivale a um ano completo.'],
 ['Fontes e anos de referência estão na tabela Cotas por país.'],
];

const cr = countries.length + 5;
setup(countrySheet, `A1:O${cr}`);
countrySheet.getRange('A2').values = [['Quantidade por país e por ano elegível']];
countrySheet.getRange('A2').format.font = { name: 'Arial', size: 14, bold: true };
countrySheet.getRange('A3').values = [['Cotas de planejamento. A aba País e ano informa o que tem calendário disponível.']];
countrySheet.getRange('A5:O5').values = [['ISO','País','População 2024','Diversidade histórica','Ano do índice','Peso de alocação','Cota principal/ano','Expansão/ano','Só população/ano','Diferença','Anos elegíveis','Entradas elegíveis','Anos sem dados','Fonte população','Fonte diversidade']];
countrySheet.getRange(`A6:O${cr}`).values = countries.map(r => [r.country_code,r.country_name,r.population_2024,r.historical_ethnic_diversity,r.diversity_reference_year,null,null,null,null,null,r.calendar_eligible_years,r.calendar_eligible_memberships,r.years_without_local_data,r.population_source,r.diversity_source]);
for (let i=6;i<=cr;i++) {
 countrySheet.getRange(`F${i}:J${i}`).formulas = [[
  `=SQRT(C${i}/1000000)*(1+0.5*D${i})`,
  `=MIN(Resumo!$B$15,Resumo!$B$14+Resumo!$B$16*INT(Resumo!$B$12*F${i}/Resumo!$B$16+1E-12))`,
  `=MIN(Resumo!$B$15,Resumo!$B$14+Resumo!$B$16*INT(Resumo!$B$13*F${i}/Resumo!$B$16+1E-12))`,
  `=MIN(Resumo!$B$15,Resumo!$B$14+Resumo!$B$16*INT(Resumo!$B$28*SQRT(C${i}/1000000)/Resumo!$B$16+1E-12))`,
  `=G${i}-I${i}`
 ]];
}
countrySheet.getRange(`C6:C${cr}`).setNumberFormat('#,##0');
countrySheet.getRange(`D6:D${cr}`).setNumberFormat('0.000');
countrySheet.getRange(`F6:F${cr}`).setNumberFormat('0.00');
countrySheet.getRange('A1:A75').format.columnWidth = 7;
countrySheet.getRange('B1:B75').format.columnWidth = 27;
countrySheet.getRange('C1:C75').format.columnWidth = 18;
countrySheet.getRange('D1:J75').format.columnWidth = 15;
countrySheet.getRange('K1:K75').format.columnWidth = 34;
countrySheet.getRange('L1:L75').format.columnWidth = 18;
countrySheet.getRange('M1:M75').format.columnWidth = 32;
countrySheet.getRange('N1:O75').format.columnWidth = 65;
header(countrySheet, 'A5:O5');
countrySheet.tables.add(`A5:O${cr}`,true,'CountryQuotas');
countrySheet.freezePanes.freezeRows(5);
countrySheet.freezePanes.freezeColumns(2);

const yr = cells.length + 5;
setup(yearSheet, `A1:N${yr}`);
yearSheet.getRange('A2').values = [['Disponibilidade e cota de cada país e ano']];
yearSheet.getRange('A2').format.font = { name: 'Arial', size: 14, bold: true };
yearSheet.getRange('A3').values = [['Zero elegível significa que o ranking exige completar o calendário. Identidades ainda precisam de revisão.']];
yearSheet.getRange('A5:N5').values = [['ISO','País','Ano','Cota principal','Itens observados','Entradas elegíveis','Plataforma','Estado do calendário','Períodos esperados','Períodos coletados','Profundidade mínima','Fim da janela','Parcela observada selecionada','Identidade']];
yearSheet.getRange(`A6:N${yr}`).values = cells.map(r => [r.country_code,r.country_name,r.year,r.quota_main,r.selected_observed_items,r.import_calendar_eligible_items,r.platform,r.status,r.expected_periods,r.collected_periods,r.minimum_depth,r.period_end,r.selected_observed_share,r.identity_status]);
yearSheet.getRange(`M6:M${yr}`).setNumberFormat('0.0%');
yearSheet.getRange('A1:A690').format.columnWidth = 7;
yearSheet.getRange('B1:B690').format.columnWidth = 27;
yearSheet.getRange('C1:C690').format.columnWidth = 9;
yearSheet.getRange('D1:G690').format.columnWidth = 16;
yearSheet.getRange('H1:H690').format.columnWidth = 47;
yearSheet.getRange('I1:K690').format.columnWidth = 18;
yearSheet.getRange('L1:M690').format.columnWidth = 22;
yearSheet.getRange('N1:N690').format.columnWidth = 52;
header(yearSheet,'A5:N5');
yearSheet.tables.add(`A5:N${yr}`,true,'CountryYearPlan');
yearSheet.freezePanes.freezeRows(5);
yearSheet.freezePanes.freezeColumns(2);

wb.recalculate();
const actual = countrySheet.getRange(`G6:J${cr}`).values;
for (let i=0;i<countries.length;i++) {
 const r=countries[i];
 const expected=[r.quota_per_year_main,r.quota_per_year_expansion,r.quota_population_only,r.diversity_quota_difference];
 if (actual[i].some((v,j)=>v!==expected[j])) throw new Error(`Quota formula differs for ${r.country_code}: ${JSON.stringify(actual[i])}`);
}
console.log((await wb.inspect({kind:'region',sheetId:'Resumo',range:'A5:B20',maxChars:2500,tableMaxRows:16,tableMaxCols:2})).ndjson);
const errors = await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#SPILL!',options:{useRegex:true,maxResults:10},maxChars:1000});
console.log(errors.ndjson);
for (const [sheetName,range,file] of [['Resumo','A1:D20','preview_summary.png'],['Cotas por país','A1:J18','preview_countries.png'],['País e ano','A1:H17','preview_years.png']]) {
 const preview=await wb.render({sheetName,range,scale:1.4,format:'png'});
 await fs.writeFile(path.join(output,file),new Uint8Array(await preview.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(path.join(output,'cotas_importacao_2017_2026.xlsx'));
console.log(JSON.stringify({xlsx:path.join(output,'cotas_importacao_2017_2026.xlsx'),countries:countries.length,cells:cells.length,formulaChecks:'passed'}));
