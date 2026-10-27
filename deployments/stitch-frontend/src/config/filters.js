import { getCountryName } from "../constants/countries";

export const FILTER_FIELDS = [
  {
    key: "country",
    label: "Country",
    formatValue: getCountryName,
    searchable: true,
  },
  { key: "region", label: "Region", searchable: true },
  { key: "state_province", label: "State/Province", searchable: true },
  { key: "basin", label: "Basin", searchable: true },
  { key: "field_status", label: "Field status" },
  { key: "primary_hydrocarbon_group", label: "Primary hydrocarbon group" },
];

export const EMPTY_FILTERS = Object.fromEntries(
  FILTER_FIELDS.map((f) => [f.key, []]),
);
