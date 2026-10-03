export function money(value: number | null | undefined): string {
  const amount = Math.round(value || 0);
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(amount);
}

export function compact(value: number | null | undefined): string {
  const amount = Math.round(value || 0);
  const sign = amount < 0 ? "−" : "";
  const absolute = Math.abs(amount);
  if (absolute >= 1_000_000) {
    const millions = absolute / 1_000_000;
    const text = millions >= 10 ? millions.toFixed(1) : millions.toFixed(2);
    return `${sign}$${text.replace(/\.00$/, "").replace(/(\.\d)0$/, "$1")}M`;
  }
  if (absolute >= 10_000) return `${sign}$${Math.round(absolute / 1000)}K`;
  return money(amount);
}

export const EVENTS: { id: string; label: string; detail: string }[] = [
  { id: "another_child", label: "Have another child", detail: "Longer dependency, and education if it is already in the plan" },
  { id: "buy_home", label: "Buy a home", detail: "Adds a mortgage preview you can replace" },
  { id: "change_jobs", label: "Change jobs", detail: "Employer coverage drops to zero" },
  { id: "raise", label: "Get a raise", detail: "Income increases 15%" },
  { id: "child_starts_college", label: "Child starts college", detail: "Oldest dependent moves to 18; remaining education is halved" },
  { id: "pay_off_debt", label: "Pay off debt", detail: "Other debt clears; the mortgage stays" },
  { id: "get_married", label: "Get married", detail: "Records a partner without guessing their income" },
  { id: "retire_earlier", label: "Retire earlier", detail: "Shortens the income-support window by 5 years" },
];

export const WHAT_IFS = [
  "What if I only want to replace my salary for 5 years?",
  "What if my employer coverage disappears?",
  "What if we decide not to include college?",
  "What if my mortgage was already paid off?",
];

export const SAMPLE =
  "I'm 36, married with two kids, make $110k, owe about $280k on my house, have $20k student debt and $200k through work.";
