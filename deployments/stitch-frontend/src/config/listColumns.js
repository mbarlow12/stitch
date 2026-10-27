import { getCountryName } from "../constants/countries";

export const COLUMNS = [
  {
    label: "Name",
    key: "name",
    className: "font-semibold text-ink",
    sortable: true,
    sortType: "string",
  },
  {
    label: "Country",
    key: "country",
    className: "text-ink-muted",
    sortable: true,
    sortType: "string",
    format: getCountryName,
  },
  {
    label: "State/Province",
    key: "state_province",
    className: "text-ink-muted",
    sortable: true,
    sortType: "string",
  },
  {
    label: "Region",
    key: "region",
    className: "text-ink-muted",
    sortable: true,
    sortType: "string",
  },
  {
    label: "Basin",
    key: "basin",
    className: "text-ink-muted",
    sortable: true,
    sortType: "string",
  },
  {
    label: "Field status",
    key: "field_status",
    className: "text-ink-muted",
    sortable: true,
    sortType: "string",
  },
  {
    label: "Primary hydrocarbon group",
    key: "primary_hydrocarbon_group",
    className: "text-ink-muted",
    sortable: true,
    sortType: "string",
  },
];

export const SORTABLE_COLUMN_KEYS = COLUMNS.filter((col) => col.sortable).map(
  (col) => col.key,
);
