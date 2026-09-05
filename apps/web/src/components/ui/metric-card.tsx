import * as React from "react";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";

export function MetricCard({ className = "", children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm hover:shadow-md transition-all duration-200 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function MetricLabel({ className = "", children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={`text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400 ${className}`} {...props}>
      {children}
    </p>
  );
}

export function MetricValue({ className = "", children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={`text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-50 mt-2 ${className}`} {...props}>
      {children}
    </h3>
  );
}

export function MetricTrend({ className = "", children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`flex items-center text-xs font-semibold mt-3 ${className}`} {...props}>
      {children}
    </div>
  );
}

export function TrendUp({ children }: { children?: React.ReactNode }) {
  return (
    <span className="flex items-center text-emerald-600 dark:text-emerald-400 font-medium">
      <ArrowUpRight className="w-4 h-4 mr-1 stroke-[2.5]" />
      {children}
    </span>
  );
}

export function TrendDown({ children }: { children?: React.ReactNode }) {
  return (
    <span className="flex items-center text-rose-600 dark:text-rose-400 font-medium">
      <ArrowDownRight className="w-4 h-4 mr-1 stroke-[2.5]" />
      {children}
    </span>
  );
}
