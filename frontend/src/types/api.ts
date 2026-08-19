export type Readability = 'readable' | 'partial' | 'unreadable';
export type CropType = 'single_book' | 'multiple_books' | 'unreadable';
export type RegionType =
  | 'book'
  | 'multiple_books'
  | 'non_book'
  | 'uncertain';
export type ReviewStatus =
  | 'high_confidence'
  | 'review_required'
  | 'unmatched';
export type ReviewReason =
  | 'read_failed'
  | 'unreadable'
  | 'no_evidence'
  | 'no_candidate'
  | 'partial_read'
  | 'low_score'
  | 'small_margin'
  | 'candidate_not_reliable_enough_to_show'
  | 'non_book'
  | 'high_confidence';

export type BookRead = {
  title: string | null;
  author: string | null;
  volume: string | null;
  raw_text: string | null;
  language: string | null;
  readability: Readability;
};

export type CatalogBook = {
  catalog_id: string;
  title: string;
  author: string;
  edition: string;
};

export type MatchCandidate = {
  catalog: CatalogBook;
  matched_title: string;
  matched_author: string | null;
  title_evidence: 'canonical' | 'alternate' | 'contained';
  title_score: number;
  author_score: number | null;
  combined_score: number;
};

export type MatchResult = {
  best_candidate: MatchCandidate | null;
  second_candidate: MatchCandidate | null;
  title_score: number | null;
  author_score: number | null;
  combined_score: number | null;
  second_score: number | null;
  margin: number | null;
  candidate_floor: number;
};

export type AnalyzedBook = {
  detection_index: number;
  book_index: number;
  read: BookRead | null;
  match: MatchResult | null;
  suggested_match: MatchCandidate | null;
  crop_type: CropType | null;
  region_type: RegionType | null;
  region_text: string | null;
  review: {
    status: ReviewStatus;
    reasons: ReviewReason[];
  };
};

export type ReviewItem = AnalyzedBook & {
  id: string;
  source_detection_indices: number[];
  duplicate_count: number;
};

type ReviewGroupBase = {
  id: string;
  title: string | null;
  author: string | null;
  review_status: ReviewStatus;
  representative_item_id: string;
  source_detection_indices: number[];
  item_count: number;
  total_entries: number;
  detection_count: number;
};

export type OrdinaryReviewGroup = ReviewGroupBase & {
  group_type: 'ordinary';
  items: ReviewItem[];
};

export type ReviewVolumeBucket = {
  id: string;
  volume: string;
  representative_item_id: string;
  items: ReviewItem[];
  source_detection_indices: number[];
  item_count: number;
  total_entries: number;
  detection_count: number;
};

export type SeriesReviewGroup = ReviewGroupBase & {
  group_type: 'series';
  volumes: ReviewVolumeBucket[];
  unknown_volume_items: ReviewItem[];
};

export type ReviewGroup = OrdinaryReviewGroup | SeriesReviewGroup;

export type CropThumbnail = {
  detection_index: number;
  data_url: string;
};

export type AnalyzeResult = {
  status: 'received';
  filename: string;
  width: number;
  height: number;
  detection_count: number;
  books: AnalyzedBook[];
  review_items: ReviewItem[];
  review_groups: ReviewGroup[];
  crop_thumbnails: CropThumbnail[];
  warnings: string[];
};

export type UploadResult = AnalyzeResult;

export type LibraryBook = {
  id: number;
  catalog_id: string | null;
  title: string;
  author: string | null;
  source: 'catalog' | 'manual';
  created_at: string;
};

export type ClearLibraryResponse = {
  deleted: number;
};
