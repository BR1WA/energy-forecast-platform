export const MOROCCO_COUNTRY = 'Morocco' as const;
export const MOROCCO_CURRENCY = 'MAD' as const;

export const MOROCCO_REGIONS = [
  'Tanger-Tétouan-Al Hoceïma',
  'Oriental',
  'Fès-Meknès',
  'Rabat-Salé-Kénitra',
  'Béni Mellal-Khénifra',
  'Casablanca-Settat',
  'Marrakech-Safi',
  'Drâa-Tafilalet',
  'Souss-Massa',
  'Guelmim-Oued Noun',
  'Laâyoune-Sakia El Hamra',
  'Dakhla-Oued Ed-Dahab',
] as const;

export type MoroccoRegion = (typeof MOROCCO_REGIONS)[number];

export function isMoroccoRegion(value: string): value is MoroccoRegion {
  return MOROCCO_REGIONS.some((region) => region === value);
}
