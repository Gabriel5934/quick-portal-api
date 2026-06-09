namespace ExcelScript {
  export type Workbook = any;
  export const CalculationType = {} as any;
}

function main(workbook: ExcelScript.Workbook) {
  const taxaSheet = workbook.getWorksheet("TAXA PADRÃO");
  const listaSheet = workbook.getWorksheet("LISTA MCCs");

  // Get unique MCCs preserving exact workbook values
  const values = listaSheet.getRange("E3:E6550").getTexts();

  const seen = new Set<string>();
  const mccs: string[] = [];

  for (let i = 0; i < values.length; i++) {
    const mcc = values[i][0];

    if (mcc !== "" && !seen.has(mcc)) {
      seen.add(mcc);
      mccs.push(mcc);
    }
  }

  const dropdown = taxaSheet.getRange("E10");
  const results: Record<string, unknown> = {};

  for (const rawMcc of mccs) {
    dropdown.setValue(rawMcc);

    workbook
      .getApplication()
      .calculate(ExcelScript.CalculationType.fullRebuild);

    const b10 = taxaSheet.getRange("B10").getText();

    if (b10 === "#N/A") {
      console.log(`Skipping "${rawMcc}" because B10 is #N/A`);
      continue;
    }

    const displayName = rawMcc.trim();

    results[displayName] = taxaSheet.getRange("M8:Q14").getValues();
  }

  console.log(JSON.stringify(results, null, 2));
}
