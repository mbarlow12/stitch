export const FIELD_META = {
  name: { label: "Name", section: "identity" },
  name_local: { label: "Local Name", section: "identity" },
  country: { label: "Country", section: "identity" },
  state_province: { label: "State / Province", section: "identity" },
  region: { label: "Region", section: "identity" },
  basin: { label: "Basin", section: "identity" },
  latitude: { label: "Latitude", section: "identity" },
  longitude: { label: "Longitude", section: "identity" },
  location_type: {
    label: "Location Type",
    section: "identity",
    options: ["Onshore", "Offshore", "Unknown"],
  },

  owners: { label: "Owner", section: "organizations" },
  operators: { label: "Operator", section: "organizations" },

  field_status: {
    label: "Field Status",
    section: "production",
    options: ["Producing", "Non-Producing", "Abandoned", "Planned"],
  },
  production_conventionality: {
    label: "Production Conventionality",
    section: "production",
    options: ["Conventional", "Unconventional", "Mixed", "Unknown"],
  },
  primary_hydrocarbon_group: {
    label: "Primary Hydrocarbon Group",
    section: "production",
    options: [
      "Ultra-Light Oil",
      "Light Oil",
      "Medium Oil",
      "Heavy Oil",
      "Extra-Heavy Oil",
      "Dry Gas",
      "Wet Gas",
      "Acid Gas",
      "Condensate",
      "Mixed",
      "Unknown",
    ],
  },
  reservoir_formation: { label: "Reservoir Formation", section: "production" },
  discovery_year: { label: "Discovery Year", section: "production" },
  production_start_year: {
    label: "Production Start Year",
    section: "production",
  },
  fid_year: { label: "FID Year", section: "production" },
};

export const IDENTITY_FIELDS = Object.entries(FIELD_META)
  .filter(([, v]) => v.section === "identity")
  .map(([k]) => k);

export const PRODUCTION_FIELDS = Object.entries(FIELD_META)
  .filter(([, v]) => v.section === "production")
  .map(([k]) => k);

export const MERGE_COMPARISON_CORE_FIELDS = [
  "name",
  "country",
  "region",
  "basin",
  "state_province",
];

const MERGE_COMPARISON_LEAD_OTHER_FIELDS = [
  "field_status",
  "production_start_year",
];

export const MERGE_COMPARISON_OTHER_FIELDS = [
  ...MERGE_COMPARISON_LEAD_OTHER_FIELDS,
  ...Object.keys(FIELD_META).filter(
    (key) =>
      !MERGE_COMPARISON_CORE_FIELDS.includes(key) &&
      !MERGE_COMPARISON_LEAD_OTHER_FIELDS.includes(key) &&
      FIELD_META[key].section !== "organizations",
  ),
];

export const AI_SUGGESTION_FIELDS = [
  "name",
  "name_local",
  "country",
  "basin",
  "region",
  "state_province",
  "reservoir_formation",
  "discovery_year",
  "fid_year",
  "production_start_year",
  "location_type",
  "field_status",
  "primary_hydrocarbon_group",
  "production_conventionality",
];
