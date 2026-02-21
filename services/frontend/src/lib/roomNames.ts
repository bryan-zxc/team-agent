const adjectives = [
  "Gentle", "Bold", "Quiet", "Swift", "Warm",
  "Bright", "Calm", "Soft", "Steady", "Golden",
  "Hidden", "Mossy", "Amber", "Misty", "Sunlit",
  "Still", "Lush", "Rosy", "Deep", "Silver",
];

const nouns = [
  "River", "Sparrow", "Meadow", "Summit", "Harbor",
  "Willow", "Ember", "Grove", "Lantern", "Hollow",
  "Ridge", "Bloom", "Cove", "Fern", "Cliff",
  "Brook", "Dune", "Pebble", "Trail", "Orchard",
];

export function generateRoomName(): string {
  const adj = adjectives[Math.floor(Math.random() * adjectives.length)];
  const noun = nouns[Math.floor(Math.random() * nouns.length)];
  return `${adj} ${noun}`;
}
