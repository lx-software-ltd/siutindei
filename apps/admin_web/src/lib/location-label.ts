/** Label shown for a venue: its name, otherwise its address. */
export function locationDisplayName(
  location: {
    name?: string | null;
    address?: string | null;
    area_id?: string | null;
  },
  fallback = ''
): string {
  const name = location.name?.trim();
  if (name) {
    return name;
  }
  const address = location.address?.trim();
  if (address) {
    return address;
  }
  return location.area_id?.trim() || fallback;
}
