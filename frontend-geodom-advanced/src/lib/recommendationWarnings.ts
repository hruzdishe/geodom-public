export function userFacingWarnings(warnings:string[]):string[] {
  return warnings.filter(message => /(?:временно недоступ|сохранённый результат|не удалось)/i.test(message))
}
