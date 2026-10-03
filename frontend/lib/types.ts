export type Source = "user" | "assumption" | "estimated" | "skipped" | "unknown" | string;

export interface Question {
  key: string;
  prompt: string;
  why: string;
  hint: string;
}

export interface ToolTrace {
  name: string;
  status: string;
  source?: string;
  detail?: string;
  fields?: string[];
  reason?: string;
}

export interface Note {
  title: string;
  source_name: string;
  source_url: string;
  content: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | string;
  content: string;
  payload: { questions?: Question[]; tools?: ToolTrace[]; notes?: Note[]; scenario_id?: string };
  created_at: string;
}

export interface Dependent {
  id?: string;
  label: string;
  age: number | null;
  education_goal: number | null;
  education_is_estimate: boolean;
}

export interface Profile {
  age: number | null;
  partner: boolean | null;
  annual_income: number | null;
  income_replacement_years: number | null;
  income_replacement_percent: number | null;
  mortgage_balance: number | null;
  mortgage_years_remaining: number | null;
  other_debt: number | null;
  existing_employer_coverage: number | null;
  existing_personal_coverage: number | null;
  savings_allocated: number | null;
  lifelong_legacy_goal: number | null;
  other_needs: number | null;
  include_education: boolean | null;
  cash_value_interest: boolean | null;
  dependents_confirmed: boolean;
  monthly_budget_preference: number | null;
  field_sources: Record<string, string>;
  dependents: Dependent[];
}

export interface MoneyRow {
  key: string;
  label: string;
  amount: number;
  detail?: string;
  blurb?: string;
}

export interface Fact {
  key: string;
  label: string;
  value: string;
  source: Source;
  editable: boolean;
}

export interface TimelinePoint {
  year_offset: number;
  calendar_year: number;
  need: number;
  gap: number;
  income: number;
  mortgage: number;
  education: number;
  debt: number;
  legacy: number;
  existing: number;
}

export interface TimelineRow {
  key: string;
  label: string;
  start: number;
  end: number;
  tone: string;
}

export interface StressItem {
  label: string;
  status: "yes" | "partial" | "no" | "skip" | string;
  detail: string;
}

export interface StressSample {
  coverage: number;
  items: StressItem[];
}

export interface Comparison {
  headline: string;
  summary: string;
  suggested_term_years: number | null;
  term: { title: string; fit: string; points: string[] };
  permanent: { title: string; fit: string; points: string[] };
  lincoln_note: string;
  sources: { title: string; url: string }[];
}

export interface Calculation {
  ready: boolean;
  completeness: string;
  formula: string;
  components: MoneyRow[];
  gross_need: number;
  resources: MoneyRow[];
  total_resources: number;
  gap: number;
  gap_low: number;
  gap_high: number;
  band_note: string;
  gap_allocation: MoneyRow[];
  resource_order_note: string;
  facts: Fact[];
  assumptions: Fact[];
  timeline: {
    start_year: number;
    horizon: number;
    points: TimelinePoint[];
    rows: TimelineRow[];
    debt_note: string;
    existing_note: string;
  };
  need_profile: {
    temporary: string;
    lifelong: string;
    cash_value: string;
    horizon_years: number;
    headline: string;
    drivers: { label: string; years: number | null; detail: string }[];
  };
  comparison: Comparison;
  stress_samples: StressSample[];
  professional_questions: string[];
  missing: { key: string; label: string; essential: boolean }[];
  children: Dependent[];
}

export interface Scenario {
  id: string;
  label: string;
  note: string;
  base_gap: number;
  scenario_gap: number;
  applied: boolean;
}

export interface AppState {
  session: { id: string; mode: "quick" | "guided"; title: string; status: string; last_question_key: string | null };
  profile: Profile;
  messages: Message[];
  calculation: Calculation;
  base_calculation: Calculation;
  active_scenario: Scenario | null;
  scenarios: Scenario[];
  questions: Question[];
}

export interface Health {
  ok: boolean;
  llm: { reachable: boolean; model: string; gpu?: string; detail?: string };
  disclaimer: string;
}
