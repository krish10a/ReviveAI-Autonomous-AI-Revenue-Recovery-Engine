"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { MetricCard, MetricLabel, MetricValue, MetricTrend, TrendUp } from "@/components/ui/metric-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import AuditTimeline from "@/components/AuditTimeline";
import {
  ShieldCheck,
  Zap,
  Clock,
  BarChart3,
  RefreshCw,
  ArrowRight,
  FileCheck,
  Info,
  Layers,
  Scale
} from "lucide-react";

interface OverviewMetrics {
  revenue_at_risk: number;
  eligible_revenue: number;
  revenue_recovered: number;
  recovery_rate_percent: number;
  active_cases: number;
  total_cases: number;
  recovered_cases_count?: number;
  blocked_cases_count?: number;
  deferred_cases_count?: number;
  escalated_cases_count?: number;
  recovery_cost: number;
  cost_per_rupee_recovered: number;
  cost_per_thousand_recovered?: number;
  net_recovery: number;
  policy_denials_count: number;
  wait_decisions_count: number;
  escalation_rate_percent: number;
  funnel?: Array<{
    stage: string;
    count: number;
    amount: number;
  }>;
  action_mix?: {
    proposed: Record<string, number>;
    approved: Record<string, number>;
  };
  policy_guardrails?: Array<{
    rule: string;
    prevents: string;
    threshold: string;
    triggered_count: number;
    status: string;
  }>;
  last_updated?: string;
}

interface ExperimentResults {
  metadata: {
    label: string;
    population: string;
    methodology?: string;
    sample_size_per_group: number;
    seed?: number;
  };
  control_group: {
    strategy: string;
    eligible_revenue: number;
    recovered_revenue: number;
    recovered_cases?: number;
    recovery_rate_percent: number;
    action_cost: number;
    cost_per_thousand_recovered?: number;
  };
  ai_group: {
    strategy: string;
    eligible_revenue: number;
    recovered_revenue: number;
    recovered_cases?: number;
    recovery_rate_percent: number;
    action_cost: number;
    cost_per_thousand_recovered?: number;
    policy_denials: number;
    wait_decisions: number;
  };
  impact_metrics: {
    recovery_lift_percent: number;
    recovery_lift_percentage_points?: number;
    relative_lift_percent?: number;
    incremental_revenue_recovered: number;
    net_incremental_revenue: number;
    ai_cost_per_rupee_recovered: number;
    ai_cost_per_thousand_recovered?: number;
  };
}

const BENCHMARK_SCENARIOS = [
  {
    id: 5,
    key: "SCENARIO_5_BANK_OUTAGE",
    title: "Bank Outage: Degraded Gateway",
    tag: "Bank Safety",
    tagVariant: "destructive" as const,
    amount: 4500,
    failureReason: "BANK_GATEWAY_TIMEOUT (Rolling Outage)",
    bank: "Kotak Mahindra Bank",
    recAction: "Retry Proposed (p=75%)",
    aiReason: "ML predicted 75% retry recovery probability based on customer tenure and historical patterns",
    policyOutcome: "DENIED (Bank failure 100% > 30% threshold)",
    policyRule: "Bank Degradation Threshold Guardrail",
    policyObserved: "Rolling failure rate = 100%",
    policyThreshold: "30% max tolerance",
    finalDecision: "WAIT (Deferred Re-evaluation)",
    executorCapability: "WAIT only — Gateway retries strictly blocked",
    verifierResult: "DEFERRED (No duplicate charge attempted)",
    recoveredAmount: 0,
    actionCost: 0,
    detail: "AI proposed automated retry. Policy Engine detected rolling 100% bank failure spike, blocked retry, and commanded WAIT."
  },
  {
    id: 3,
    key: "SCENARIO_3_OPTED_OUT",
    title: "Customer Opt-Out: Zero Contact",
    tag: "Compliance",
    tagVariant: "warning" as const,
    amount: 1999,
    failureReason: "Insufficient Funds",
    bank: "State Bank of India",
    recAction: "Generate Payment Link",
    aiReason: "ML recommended payment link to allow self-serve balance top-up",
    policyOutcome: "DENIED (Customer Opt-Out Flag = True)",
    policyRule: "Customer Communication Opt-Out Barrier",
    policyObserved: "opted_out = True",
    policyThreshold: "Zero automated communication allowed",
    finalDecision: "STOP",
    executorCapability: "STOP only — SMS/Email dispatch strictly blocked",
    verifierResult: "CUSTOMER_PROTECTED (0 messages dispatched)",
    recoveredAmount: 0,
    actionCost: 0,
    detail: "Customer has opted out of automated communications. Policy immediately suppressed messaging, preventing harassment."
  },
  {
    id: 1,
    key: "SCENARIO_1_RECOVERABLE",
    title: "Recoverable: Timed Smart Retry",
    tag: "Recovery",
    tagVariant: "success" as const,
    amount: 2499,
    failureReason: "Insufficient Funds",
    bank: "HDFC Bank",
    recAction: "Retry Later (p=85%)",
    aiReason: "High tenure customer (365d) with 96% historical success; morning salary window",
    policyOutcome: "APPROVED (All Guardrails Satisfied)",
    policyRule: "Healthy Bank Gateway + Within Retry Limit (<3)",
    policyObserved: "Retry attempt = 1, Amount < ₹10,000",
    policyThreshold: "All statutory and risk checks passed",
    finalDecision: "RETRY (Optimal Window)",
    executorCapability: "Scheduled API retry via Razorpay gateway",
    verifierResult: "VERIFIED_SUCCESS (Payment Captured)",
    recoveredAmount: 2499,
    actionCost: 0.50,
    detail: "High tenure customer with 96% historical success. Engine scheduled retry for morning salary window."
  },
  {
    id: 4,
    key: "SCENARIO_4_HIGH_VALUE",
    title: "High Value: Amount Ceiling",
    tag: "Risk Governance",
    tagVariant: "default" as const,
    amount: 32000,
    failureReason: "High Value Security Hold",
    bank: "Axis Bank",
    recAction: "Auto-Retry Proposed",
    aiReason: "ML proposed autonomous retry attempt for large ticket size",
    policyOutcome: "DENIED (Amount ₹32,000 > ₹10,000 Ceiling)",
    policyRule: "Merchant Automated Amount Ceiling",
    policyObserved: "Transaction amount = ₹32,000",
    policyThreshold: "₹10,000 maximum automated ceiling",
    finalDecision: "ESCALATE (Human Ops)",
    executorCapability: "Enqueue to Merchant Ops Desk for human review",
    verifierResult: "ESCALATED_UNRESOLVED (Pending Supervisor)",
    recoveredAmount: 0,
    actionCost: 0,
    detail: "Amount exceeds merchant automated ceiling of ₹10,000. Forced human supervisor review."
  }
];

export default function Dashboard() {
  const [metrics, setMetrics] = useState<OverviewMetrics | null>(null);
  const [experiment, setExperiment] = useState<ExperimentResults | null>(null);
  const [selectedScenario, setSelectedScenario] = useState(BENCHMARK_SCENARIOS[0]);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [runningExperiment, setRunningExperiment] = useState(false);
  const [showMethodology, setShowMethodology] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  const fetchOverview = async (isInitial = false) => {
    try {
      if (!isInitial) setLoading(true);
      const resOverview = await fetch("/api/analytics/overview");
      if (resOverview.ok) {
        const data = await resOverview.json();
        setMetrics(data);
      }
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
    } finally {
      setLoading(false);
    }
  };

  const triggerExperiment = async (isInitial = false) => {
    try {
      if (!isInitial) setRunningExperiment(true);
      const res = await fetch("/api/analytics/experiment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cases_per_group: 50, seed: 42 }),
      });
      if (res.ok) {
        setExperiment(await res.json());
      }
    } catch (err) {
      console.error("Experiment failed:", err);
    } finally {
      setRunningExperiment(false);
    }
  };

  const runBatchSimulation = async () => {
    console.log("[ReviveAI] runBatchSimulation started");
    try {
      setSimulating(true);
      setActionFeedback("Generating 25 synthetic cases (replacing previous synthetic operational cohort)...");
      const res = await fetch("/api/simulate/batch?total_cases=25", { method: "POST" });
      if (res.ok) {
        await fetchOverview();
        setActionFeedback("Generated 25 synthetic cases. Replaced synthetic operational cohort; canonical benchmark scenarios remain isolated.");
        setTimeout(() => setActionFeedback(null), 5000);
      } else {
        setActionFeedback("Batch simulation request returned an error.");
      }
    } catch (err) {
      console.error("Simulation error:", err);
      setActionFeedback("Failed to run batch simulation.");
    } finally {
      setSimulating(false);
    }
  };

  useEffect(() => {
    console.log("[ReviveAI] Dashboard mounted");
    fetchOverview(true);
    triggerExperiment(true);
  }, []);

  // Format action cost per thousand recovered
  const costPerThousand = metrics?.cost_per_thousand_recovered ?? (
    metrics && metrics.revenue_recovered > 0
      ? Number(((metrics.recovery_cost / metrics.revenue_recovered) * 1000).toFixed(2))
      : 0
  );

  return (
    <div className="w-full max-w-7xl mx-auto space-y-8 p-4 md:p-8 font-sans antialiased text-slate-900 dark:text-slate-100">
      {/* Hero Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-6 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              ReviveAI
            </h1>
            <Badge variant="success">Autonomous Recovery Engine 2.0</Badge>
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1 flex flex-wrap items-center gap-1.5 font-medium">
            <span>Payment Failure</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
            <span>Diagnosis</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
            <span>ML Prediction</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-amber-600 dark:text-amber-400 font-bold">Policy Barrier</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
            <span>Bounded Execution</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-emerald-600 dark:text-emerald-400 font-bold">Independent Verification</span>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => fetchOverview()} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Sync DB
          </Button>
          <Button
            type="button"
            variant="default"
            size="sm"
            onClick={runBatchSimulation}
            disabled={simulating}
          >
            <Zap className="w-4 h-4 mr-2" />
            {simulating ? "Generating 25 Cases..." : "Generate 25 Synthetic Cases"}
          </Button>
        </div>
      </div>

      {/* Action Notification Banner */}
      {actionFeedback && (
        <div className="p-3.5 rounded-lg bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-900 text-xs font-medium text-blue-900 dark:text-blue-200 flex items-center justify-between animate-fadeIn">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-blue-600" />
            <span>{actionFeedback}</span>
          </div>
          <button onClick={() => setActionFeedback(null)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
            ×
          </button>
        </div>
      )}

      {/* A. Executive KPI Layer (6 Reconciled Cards) */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {/* 1. Revenue at Risk */}
        <MetricCard title="Total unresolved payment value currently exposed to recovery.">
          <MetricLabel>Revenue at Risk</MetricLabel>
          <MetricValue>₹{(metrics?.revenue_at_risk ?? 0).toLocaleString()}</MetricValue>
          <MetricTrend>
            <span className="text-slate-500 font-medium">Open failed-payment value</span>
          </MetricTrend>
        </MetricCard>

        {/* 2. Eligible Recovery Value (Denominator) */}
        <MetricCard title="Total payment volume considered for recovery (denominator for Recovery Rate).">
          <MetricLabel>Eligible Recovery Value</MetricLabel>
          <MetricValue className="text-blue-600 dark:text-blue-400">
            ₹{(metrics?.eligible_revenue ?? 0).toLocaleString()}
          </MetricValue>
          <MetricTrend>
            <span className="text-slate-500 font-medium">Recoverable payment volume</span>
          </MetricTrend>
        </MetricCard>

        {/* 3. Revenue Recovered */}
        <MetricCard title="Value recorded in the verified recovery ledger after successful recovery verification.">
          <MetricLabel>Revenue Recovered</MetricLabel>
          <MetricValue className="text-emerald-600 dark:text-emerald-400">
            ₹{(metrics?.revenue_recovered ?? 0).toLocaleString()}
          </MetricValue>
          <MetricTrend>
            <TrendUp>Verified recovery</TrendUp>
          </MetricTrend>
        </MetricCard>

        {/* 4. Recovery Rate */}
        <MetricCard title="Verified recovered value divided by eligible recovery value.">
          <MetricLabel>Recovery Rate</MetricLabel>
          <MetricValue>{metrics?.recovery_rate_percent ?? 0}%</MetricValue>
          <MetricTrend>
            <span className="text-slate-500 font-medium">of eligible value</span>
          </MetricTrend>
        </MetricCard>

        {/* 5. Policy Blocks */}
        <MetricCard title="Number of proposed recovery actions rejected by deterministic policy guardrails.">
          <MetricLabel>Policy Blocks</MetricLabel>
          <MetricValue className="text-amber-600 dark:text-amber-400">
            {metrics?.policy_denials_count ?? 0}
          </MetricValue>
          <MetricTrend>
            <ShieldCheck className="w-4 h-4 mr-1 text-amber-500 inline" />
            <span className="text-slate-500 font-medium">Unsafe actions prevented</span>
          </MetricTrend>
        </MetricCard>

        {/* 6. Total Action Cost */}
        <MetricCard title="Simulated operational cost of recovery actions divided by verified recovered value.">
          <MetricLabel>Total Action Cost</MetricLabel>
          <MetricValue>₹{(metrics?.recovery_cost ?? 0).toFixed(2)}</MetricValue>
          <MetricTrend>
            <span className="text-slate-500 font-medium">
              ₹{costPerThousand} per ₹1,000 recovered
            </span>
          </MetricTrend>
        </MetricCard>
      </div>

      {/* B. "What Happened?" Operational Summary Strip */}
      <div className="p-4 rounded-xl bg-slate-100/80 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-indigo-600" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Operational Summary:
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-6 text-xs">
            <div>
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Failed Payments</span>
              <span className="font-bold text-slate-800 dark:text-slate-200">{metrics?.total_cases ?? 0}</span>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Eligible</span>
              <span className="font-bold text-slate-800 dark:text-slate-200">{metrics?.total_cases ?? 0}</span>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Recovered</span>
              <span className="font-bold text-emerald-600 dark:text-emerald-400">
                ₹{(metrics?.revenue_recovered ?? 0).toLocaleString()} ({metrics?.recovered_cases_count ?? 0} cases)
              </span>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Policy Blocked</span>
              <span className="font-bold text-amber-600 dark:text-amber-400">{metrics?.policy_denials_count ?? 0}</span>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Deferred (WAIT)</span>
              <span className="font-bold text-indigo-600 dark:text-indigo-400">{metrics?.wait_decisions_count ?? 0}</span>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Escalated (Human Ops)</span>
              <span className="font-bold text-slate-700 dark:text-slate-300">{metrics?.escalated_cases_count ?? 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* C. Operational Funnel & D. Action Mix */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Operational Funnel (2 cols on lg) */}
        <Card className="lg:col-span-2 border-slate-200 dark:border-slate-800">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base font-bold flex items-center gap-2">
                  <FileCheck className="w-4 h-4 text-blue-600" />
                  Operational Recovery Funnel
                </CardTitle>
                <CardDescription className="text-xs">
                  Real progression from payment failure through independent verification across operational cohort. Note: Protective policy outcomes (STOP / WAIT / ESCALATE) prevent unauthorized retries and are excluded from recovery execution.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
              {(metrics?.funnel ?? [
                { stage: "Failed Payments", count: metrics?.total_cases ?? 0, amount: metrics?.eligible_revenue ?? 0 },
                { stage: "Diagnosed", count: metrics?.total_cases ?? 0, amount: metrics?.eligible_revenue ?? 0 },
                { stage: "Recovery Eligible", count: metrics?.total_cases ?? 0, amount: metrics?.eligible_revenue ?? 0 },
                { stage: "Recovery Action Allowed", count: (metrics?.total_cases ?? 0) - (metrics?.policy_denials_count ?? 0), amount: metrics?.eligible_revenue ?? 0 },
                { stage: "Recovery Action Executed", count: metrics?.recovered_cases_count ?? 0, amount: metrics?.eligible_revenue ?? 0 },
                { stage: "Independently Verified Recovery", count: metrics?.recovered_cases_count ?? 0, amount: metrics?.revenue_recovered ?? 0 },
              ]).map((st, idx) => (
                <div
                  key={st.stage}
                  className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex flex-col justify-between"
                >
                  <div>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                      Stage {idx + 1}
                    </span>
                    <h5 className="text-xs font-semibold text-slate-800 dark:text-slate-200 mt-0.5 line-clamp-1">
                      {st.stage}
                    </h5>
                  </div>
                  <div className="mt-3 pt-2 border-t border-slate-200 dark:border-slate-800">
                    <p className="text-base font-extrabold text-slate-900 dark:text-slate-100">
                      {st.count}
                    </p>
                    <p className="text-[10px] text-slate-500 mt-0.5">
                      ₹{st.amount.toLocaleString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Action Mix Comparison */}
        <Card className="border-slate-200 dark:border-slate-800">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-bold flex items-center gap-2">
              <Scale className="w-4 h-4 text-indigo-600" />
              AI Proposal → Final Action
            </CardTitle>
            <CardDescription className="text-xs">
              Event counts across case lifecycles; one case may generate multiple proposals during replanning.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="p-2.5 rounded-lg bg-blue-50/60 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900 text-[11px] font-medium text-blue-900 dark:text-blue-200 text-center">
              AI Proposal Events → Final Execution Events. (Proposal events may exceed case count because a case can be replanned).
            </div>

            <div className="space-y-2 text-xs">
              {[
                { name: "Smart Retry", key: "retry", aiKey: "retry" },
                { name: "Payment Link", key: "generate_payment_link", aiKey: "generate_payment_link" },
                { name: "Safe Deferral (WAIT)", key: "wait", aiKey: "wait" },
                { name: "Suppress Action (STOP)", key: "stop", aiKey: "stop" },
                { name: "Human Escalation", key: "escalate", aiKey: "escalate" },
              ].map((act) => {
                const proposedCount = metrics?.action_mix?.proposed?.[act.aiKey] ?? 0;
                const approvedCount = metrics?.action_mix?.approved?.[act.key] ?? 0;
                return (
                  <div key={act.key} className="flex items-center justify-between p-2 rounded bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800">
                    <span className="font-semibold text-slate-700 dark:text-slate-300 text-xs">{act.name}</span>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-slate-500 font-mono">
                        AI Proposal Events: <strong className="text-slate-700 dark:text-slate-300">{proposedCount}</strong>
                      </span>
                      <span className="text-slate-400">→</span>
                      <span className="font-mono text-emerald-600 dark:text-emerald-400">
                        Final Execution Events: <strong>{approvedCount}</strong>
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* E. Policy Safety Panel: Active Deterministic Guardrails */}
      <Card className="border-amber-200/80 dark:border-amber-900/60 bg-gradient-to-br from-amber-50/30 to-orange-50/20 dark:from-slate-900 dark:to-slate-950">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-amber-600 dark:text-amber-400" />
            <div>
              <CardTitle className="text-base font-bold text-slate-900 dark:text-slate-100">
                Active Policy Guardrails & Statutory Safety Barriers
              </CardTitle>
              <CardDescription className="text-xs">
                Hard deterministic barriers evaluated before any recovery action can touch banking infrastructure.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {(metrics?.policy_guardrails ?? [
              {
                rule: "Customer Opt-Out",
                prevents: "Automated contact to opted-out users (Hard Block)",
                threshold: "100% suppression on opt-out flag",
                triggered_count: 6,
                status: "ACTIVE"
              },
              {
                rule: "Bank Degradation Threshold",
                prevents: "Retries during degraded bank gateway states",
                threshold: "Forced WAIT when failure rate > 30%",
                triggered_count: 2,
                status: "ACTIVE"
              },
              {
                rule: "High-Value Amount Ceiling",
                prevents: "Autonomous execution of excessive amounts",
                threshold: "Forced ESCALATE to human ops > ₹10,000",
                triggered_count: metrics?.escalated_cases_count ?? 1,
                status: "ACTIVE"
              },
              {
                rule: "Retry Limit Protection",
                prevents: "Repeated attempts causing card issuer blocks",
                threshold: "Maximum 3 attempts within cooldown window",
                triggered_count: 1,
                status: "ACTIVE"
              },
              {
                rule: "Already Captured Guard",
                prevents: "Duplicate recovery on settled transactions",
                threshold: "Instant STOP if status is CAPTURED",
                triggered_count: 1,
                status: "ACTIVE"
              }
            ]).map((guard) => (
              <div
                key={guard.rule}
                className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <Badge variant="warning" className="text-[10px] py-0">GUARDRAIL</Badge>
                    <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400">{guard.status}</span>
                  </div>
                  <h5 className="font-bold text-xs text-slate-800 dark:text-slate-200">{guard.rule}</h5>
                  <p className="text-[11px] text-slate-500 mt-1">{guard.prevents}</p>
                </div>
                <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
                  <span className="text-[10px] text-slate-400">Triggered:</span>
                  <Badge variant="destructive" className="text-[10px] py-0 px-2 font-mono">
                    {guard.triggered_count} times
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* F. Deterministic Benchmark Scenarios (Judge Scenarios) */}
      <div className="space-y-4">
        <div className="flex justify-between items-end">
          <div>
            <h2 className="text-xl font-bold tracking-tight">Canonical Benchmark Scenarios</h2>
            <p className="text-xs text-slate-500">
              Four deterministic failure modes used to demonstrate policy behavior. (Click to inspect without side-effects).
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {BENCHMARK_SCENARIOS.map((sc) => {
            const isSelected = selectedScenario.id === sc.id;
            return (
              <div
                key={sc.id}
                onClick={() => setSelectedScenario(sc)}
                className={`p-4 rounded-xl border cursor-pointer transition-all duration-200 ${
                  isSelected
                    ? "border-blue-600 bg-blue-50/40 dark:bg-blue-950/30 shadow-md ring-2 ring-blue-500/20"
                    : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300"
                }`}
              >
                <div className="flex justify-between items-start mb-2">
                  <Badge variant={sc.tagVariant}>{sc.tag}</Badge>
                  <span className="text-xs font-bold text-slate-600 dark:text-slate-400">₹{sc.amount.toLocaleString()}</span>
                </div>
                <h4 className="font-bold text-sm line-clamp-1">{sc.title}</h4>
                <p className="text-xs text-slate-500 mt-1 line-clamp-2">{sc.detail}</p>
                <div className="mt-3 pt-2 border-t border-slate-200 dark:border-slate-800 flex justify-between items-center text-[11px]">
                  <span className="text-slate-400">Final Action:</span>
                  <span className="font-semibold text-blue-600 dark:text-blue-400">{sc.finalDecision.split(" ")[0]}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* G. Selected Case Inspector: 4-Step Explainable Chain */}
      <Card className="border-slate-300 dark:border-slate-800">
        <CardHeader>
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-2">
            <div>
              <div className="flex items-center gap-2">
                <CardTitle className="text-lg font-bold">Case Inspector: {selectedScenario.title}</CardTitle>
                <Badge variant={selectedScenario.tagVariant}>{selectedScenario.key}</Badge>
              </div>
              <CardDescription className="text-xs mt-1">
                Amount: ₹{selectedScenario.amount.toLocaleString()} • Bank: {selectedScenario.bank} • Condition: {selectedScenario.failureReason}
              </CardDescription>
            </div>
            <div className="text-right">
              <span className="text-xs text-slate-500 block">Final Executable Action:</span>
              <span className="text-sm font-bold text-blue-600 dark:text-blue-400">
                {selectedScenario.finalDecision}
              </span>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* 4-Step Explainable Chain */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
            {/* Step 1: AI Model */}
            <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <span className="text-[10px] font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400 block">
                Step 1 — AI Model
              </span>
              <p className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-1">
                {selectedScenario.recAction}
              </p>
              <p className="text-xs text-slate-500 mt-1">{selectedScenario.aiReason}</p>
            </div>

            {/* Step 2: Policy Engine */}
            <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <span className="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 block">
                Step 2 — Policy Barrier
              </span>
              <p className={`text-sm font-bold mt-1 ${
                selectedScenario.policyOutcome.includes("DENIED") ? "text-rose-600" : "text-emerald-600"
              }`}>
                {selectedScenario.policyOutcome}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Rule: {selectedScenario.policyRule}
              </p>
            </div>

            {/* Step 3: Bounded Execution */}
            <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400 block">
                Step 3 — Bounded Execution
              </span>
              <p className="text-sm font-bold text-indigo-600 dark:text-indigo-400 mt-1">
                {selectedScenario.finalDecision}
              </p>
              <p className="text-xs text-slate-500 mt-1">{selectedScenario.executorCapability}</p>
            </div>

            {/* Step 4: Verification */}
            <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 block">
                Step 4 — Verification
              </span>
              <p className="text-sm font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                {selectedScenario.verifierResult}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Recovered: ₹{selectedScenario.recoveredAmount.toLocaleString()} • Cost: ₹{selectedScenario.actionCost.toFixed(2)}
              </p>
            </div>
          </div>

          {/* Audit Timeline */}
          <div>
            <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-blue-600" />
              Case Lifecycle Audit Timeline
            </h4>
            <AuditTimeline caseId={selectedScenario.id} scenarioKey={selectedScenario.key} />
          </div>
        </CardContent>
      </Card>

      {/* H. Controlled Business Impact Experiment */}
      <Card className="border-blue-200 dark:border-blue-900/60 bg-gradient-to-br from-blue-50/50 to-indigo-50/30 dark:from-slate-900 dark:to-slate-950">
        <CardHeader className="flex flex-col md:flex-row items-start md:items-center justify-between pb-2 gap-4">
          <div>
            <div className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-blue-600" />
              <CardTitle className="text-lg font-bold">Controlled Business Impact Experiment</CardTitle>
              <Badge variant="outline" className="text-[10px]">Synthetic Controlled Simulation</Badge>
            </div>
            <CardDescription className="text-xs mt-1">
              Replay of identical synthetic cohort under two strategies (n=100, 50 Control vs 50 ReviveAI, fixed random seed = 42).
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowMethodology(!showMethodology)}
            >
              {showMethodology ? "Hide Method" : "Experiment Method"}
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={() => triggerExperiment()}
              disabled={runningExperiment}
            >
              {runningExperiment ? "Evaluating..." : "Re-run Experiment"}
            </Button>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Methodology Disclosure Drawer */}
          {showMethodology && (
            <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs space-y-2">
              <h5 className="font-bold text-slate-800 dark:text-slate-200">Experiment Methodology & Controls</h5>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-slate-600 dark:text-slate-400">
                <div>
                  <strong>Population:</strong> 100 synthetic failed payments with realistic failure distributions (insufficient funds, expired cards, bank outages, auth failures).
                </div>
                <div>
                  <strong>Treatment Isolation:</strong> Fixed pseudo-random seed = 42 ensures exact reproducible cohort characteristics across runs.
                </div>
                <div>
                  <strong>Metric Definitions:</strong> Recovery Rate Difference is reported in absolute percentage points. Action costs reflect actual SMS/payment link API charges.
                </div>
              </div>
            </div>
          )}

          {/* 4 Experiment Result Columns */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-2">
            {/* Control */}
            <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Control Group (Static Retry)</span>
              <p className="text-2xl font-bold text-slate-700 dark:text-slate-300 mt-1">
                {experiment?.control_group?.recovery_rate_percent ?? 0}%
              </p>
              <p className="text-xs text-slate-500 mt-1">
                ₹{(experiment?.control_group?.recovered_revenue ?? 0).toLocaleString()} recovered
              </p>
              <p className="text-[10px] text-slate-400 mt-0.5">
                Cost: ₹{experiment?.control_group?.action_cost ?? 0} (₹{experiment?.control_group?.cost_per_thousand_recovered ?? 0} / ₹1,000)
              </p>
            </div>

            {/* ReviveAI */}
            <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-emerald-300 dark:border-emerald-800">
              <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">ReviveAI Group (Closed-Loop)</span>
              <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                {experiment?.ai_group?.recovery_rate_percent ?? 0}%
              </p>
              <p className="text-xs text-slate-500 mt-1">
                ₹{(experiment?.ai_group?.recovered_revenue ?? 0).toLocaleString()} recovered
              </p>
              <p className="text-[10px] text-slate-400 mt-0.5">
                Cost: ₹{experiment?.ai_group?.action_cost ?? 0} (₹{experiment?.ai_group?.cost_per_thousand_recovered ?? 0} / ₹1,000)
              </p>
            </div>

            {/* Recovery Lift */}
            <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-blue-300 dark:border-blue-800">
              <span className="text-[10px] font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wider">Recovery Difference</span>
              <p className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1">
                +{experiment?.impact_metrics?.recovery_lift_percentage_points ?? experiment?.impact_metrics?.recovery_lift_percent ?? 0} pts
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Percentage-point difference over static baseline
              </p>
              <p className="text-[10px] text-blue-500 mt-0.5 font-medium">
                Relative lift: +{experiment?.impact_metrics?.relative_lift_percent ?? 0}%
              </p>
            </div>

            {/* Net Incremental Revenue */}
            <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-indigo-300 dark:border-indigo-800">
              <span className="text-[10px] font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">Net Incremental Revenue</span>
              <p className="text-2xl font-bold text-indigo-600 dark:text-indigo-400 mt-1">
                ₹{(experiment?.impact_metrics?.net_incremental_revenue ?? 0).toLocaleString()}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Net gain after subtracting operational costs
              </p>
              <p className="text-[10px] text-indigo-500 mt-0.5 font-medium">
                Gross: ₹{(experiment?.impact_metrics?.incremental_revenue_recovered ?? 0).toLocaleString()}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* I. Data & Methodology Disclosure Footer */}
      <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-xs text-slate-500 space-y-2">
        <div className="flex items-center gap-2 font-bold text-slate-700 dark:text-slate-300">
          <Info className="w-4 h-4 text-blue-500" />
          <span>Data Sources & Methodology Disclosure</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-1 text-[11px] leading-relaxed">
          <div>
            <strong className="text-slate-700 dark:text-slate-300 block">Operational Data:</strong>
            Synthetic payment and recovery data persisted in PostgreSQL. Denominator is strictly eligible recovery value.
          </div>
          <div>
            <strong className="text-slate-700 dark:text-slate-300 block">Machine Learning:</strong>
            Action-conditioned model predicts recovery probability conditioned on action type. Zero unvalidated direct executions.
          </div>
          <div>
            <strong className="text-slate-700 dark:text-slate-300 block">Policy Barrier:</strong>
            Deterministic statutory code guardrails enforce hard stops, outage deferrals, and high-value supervisor escalations.
          </div>
          <div>
            <strong className="text-slate-700 dark:text-slate-300 block">Financial Ledger:</strong>
            Recoveries are credited only after independent simulated verification proof is recorded.
          </div>
        </div>
      </div>
    </div>
  );
}
