import type { ContentBlock } from "./api";

export type HomebrewSortField = "title" | "content_type" | "karma_cost" | "source_url" | "notes";
export type HomebrewSortDirection = "asc" | "desc";
export type HomebrewSortState = { field: HomebrewSortField; direction: HomebrewSortDirection };

export function homebrewKarmaSortKey(entry: Partial<ContentBlock> & { status_text?: string }): { group: number; value: number };
export function compareHomebrewKarma(left: ContentBlock, right: ContentBlock, direction: HomebrewSortDirection): number;
export function nextHomebrewSort(current: HomebrewSortState, field: HomebrewSortField): HomebrewSortState;
