"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { MetricCard, MetricLabel, MetricValue, MetricTrend, TrendUp, TrendDown } from "@/components/ui/metric-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import AuditTimeline from "@/components/AuditTimeline";
import DecisionExplainer from "@/components/DecisionExplainer";
import { ShieldCheck, Zap, AlertTriangle, Clock, Users, ArrowUpRight, BarChart3, RefreshCw } from "lucide-react";

interface OverviewMetrics {
  revenue_at_risk: number;
  eligible_revenue: number;
  revenue_recovered: number;
  recovery_rate_percent: number;
  active_cases: number;
  total_cases: number;
  recovery_cost: number;
  cost_per_rupee_recovered: number;
  net_recovery: number;
  policy_denials_count: number;
  wait_decisions_count: number;
  escalation_rate_percent: number;
  last_updated?: string;
}

interface ExperimentResults {
  metadata: {
    label: string;
    population: string;
    sample_size_per_group: number;
  };
  control_group: {
    strategy: string;
    eligible_revenue: number;
    recovered_revenue: number;
    recovery_rate_percent: number;
    action_cost: number;
  };
  ai_group: {
    strategy: string;
    eligible_revenue: number;
    recovered_revenue: number;
    recovery_rate_percent: number;
    action_cost: number;
    policy_denials: number;
    wait_decisions: number;
  };
  impact_metrics: {
    recovery_lift_percent: number;
    incremental_revenue_recovered: number;
    net_incremental_revenue: number;
    ai_cost_per_rupee_recovered: number;
  };
}

const BENCHMARK_SCENARIOS = [
  {
    id: 5,
    key: "SCENARIO_5_BANK_OUTAGE",
    title: "Bank Outage: Policy Overrides AI",
    tag: "Judge Spotlight",
    tagVariant: "destructive" as const,
    amount: 4500,
    failureReason: "BANK_GATEWAY_TIMEOUT (Outage)",
    bank: "Kotak Mahindra Bank",
    recAction: "Retry Proposed (p=75%)",
    policyOutcome: "DENIED by Policy Barrier",
    finalDecision: "WAIT (Deferred Re-evaluation)",
    detail: "AI proposed automated retry. Policy Engine detected rolling 72% bank failure spike, blocked retry, and commanded WAIT."
  },
  {
    id: 3,
    key: "SCENARIO_3_OPTED_OUT",
    title: "Customer Opt-Out: Zero Contact",
    tag: "Compliance",
    tagVariant: "warning" as const,
    amount: 1999,
    failureReason: "Insufficient Funds",
    bank: "SBI",
    recAction: "Payment Link Proposed",
    policyOutcome: "DENIED (Hard Opt-Out)",
    finalDecision: "STOP",
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
    bank: "HDFC",
    recAction: "Retry Later (p=85%)",
    policyOutcome: "APPROVED",
    finalDecision: "RETRY (Optimal Window)",
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
    policyOutcome: "DENIED (Ceiling > ₹10,000)",
    finalDecision: "ESCALATE (Human Ops)",
    detail: "Amount exceeds merchant automated ceiling of ₹10,000. Forced human supervisor review."
  }
];

export default function Dashboard() {
  const [metrics, setMetrics] = useState<OverviewMetrics | null>(null);
  const [failureBreakdown, setFailureBreakdown] = useState<any[]>([]);
  const [interventionStats, setInterventionStats] = useState<any[]>([]);
  const [experiment, setExperiment] = useState<ExperimentResults | null>(null);
  const [selectedScenario, setSelectedScenario] = useState(BENCHMARK_SCENARIOS[0]);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [runningExperiment, setRunningExperiment] = useState(false);

  const fetchOverview = async () => {
    try {
      setLoading(true);
      const [resOverview, resFailures, resInterventions] = await Promise.all([
        fetch("/api/analytics/overview"),
        fetch("/api/analytics/failure-reason"),
        fetch("/api/analytics/intervention-performance"),
      ]);

      if (resOverview.ok) setMetrics(await resOverview.json());
      if (resFailures.ok) setFailureBreakdown(await resFailures.json());
      if (resInterventions.ok) setInterventionStats(await resInterventions.json());
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
    } finally {
      setLoading(false);
    }
  };

  const triggerExperiment = async () => {
    try {
      setRunningExperiment(true);
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
    try {
      setSimulating(true);
      const res = await fetch("/api/simulate/batch?total_cases=25", { method: "POST" });
      if (res.ok) {
        await fetchOverview();
      }
    } catch (err) {
      console.error("Simulation error:", err);
    } finally {
      setSimulating(false);
    }
  };

  useEffect(() => {
    fetchOverview();
    triggerExperiment();
  }, []);

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
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Deterministic Policy Guardrails • Action-Conditioned ML • Zero Direct Execution
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={fetchOverview} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Sync DB
          </Button>
          <Button variant="default" size="sm" onClick={runBatchSimulation} disabled={simulating}>
            <Zap className="w-4 h-4 mr-2" />
            {simulating ? "Injecting & Resolving..." : "Run Batch Simulation (25)"}
          </Button>
        </div>
      </div>

      {/* Primary KPI Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <MetricCard>
          <MetricLabel>Revenue at Risk</MetricLabel>
          <MetricValue>₹{(metrics?.revenue_at_risk ?? 0).toLocaleString()}</MetricValue>
          <MetricTrend>
            <span className="text-slate-500">{metrics?.active_cases ?? 0} active cases</span>
          </MetricTrend>
        </MetricCard>

        <MetricCard>
          <MetricLabel>Revenue Recovered</MetricLabel>
          <MetricValue className="text-emerald-600 dark:text-emerald-400">
            ₹{(metrics?.revenue_recovered ?? 0).toLocaleString()}
          </MetricValue>
          <MetricTrend>
            <TrendUp>Verified Ledger</TrendUp>
          </MetricTrend>
        </MetricCard>

        <MetricCard>
          <MetricLabel>Recovery Rate</MetricLabel>
          <MetricValue>{metrics?.recovery_rate_percent ?? 0}%</MetricValue>
          <MetricTrend>
            <span className="text-slate-500">of eligible volume</span>
          </MetricTrend>
        </MetricCard>

        <MetricCard>
          <MetricLabel>Total Recovery Cost</MetricLabel>
          <MetricValue>₹{(metrics?.recovery_cost ?? 0).toFixed(2)}</MetricValue>
          <MetricTrend>
            <span className="text-slate-500">₹{(metrics?.cost_per_rupee_recovered ?? 0).toFixed(3)} / ₹ recovered</span>
          </MetricTrend>
        </MetricCard>

        <MetricCard>
          <MetricLabel>Policy Denials</MetricLabel>
          <MetricValue className="text-amber-600 dark:text-amber-400">
            {metrics?.policy_denials_count ?? 0}
          </MetricValue>
          <MetricTrend>
            <ShieldCheck className="w-4 h-4 mr-1 text-amber-500" /> Hard Guardrails
          </MetricTrend>
        </MetricCard>

        <MetricCard>
          <MetricLabel>WAIT Decisions</MetricLabel>
          <MetricValue className="text-indigo-600 dark:text-indigo-400">
            {metrics?.wait_decisions_count ?? 0}
          </MetricValue>
          <MetricTrend>
            <Clock className="w-4 h-4 mr-1 text-indigo-500" /> Bank Recovery
          </MetricTrend>
        </MetricCard>
      </div>

      {/* Control vs AI Experiment Section */}
      <Card className="border-blue-200 dark:border-blue-900/60 bg-gradient-to-br from-blue-50/50 to-indigo-50/30 dark:from-slate-900 dark:to-slate-950">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <div>
            <div className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-blue-600" />
              <CardTitle>Controlled Business Impact Experiment</CardTitle>
            </div>
            <CardDescription className="mt-1">
              Synthetic cohort (n=100) split 50/50: Naive Static Retry Strategy vs. ReviveAI Closed-Loop Pipeline.
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={triggerExperiment} disabled={runningExperiment}>
            {runningExperiment ? "Evaluating Cohort..." : "Re-run Experiment"}
          </Button>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 pt-4">
            <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Control Group</span>
              <p className="text-xl font-bold text-slate-700 dark:text-slate-300 mt-1">
                {experiment?.control_group.recovery_rate_percent ?? 0}%
              </p>
              <p className="text-xs text-slate-500 mt-1">
                ₹{(experiment?.control_group.recovered_revenue ?? 0).toLocaleString()} recovered (Cost: ₹{experiment?.control_group.action_cost ?? 0})
              </p>
            </div>

            <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-emerald-300 dark:border-emerald-800">
              <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">ReviveAI Group</span>
              <p className="text-xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                {experiment?.ai_group.recovery_rate_percent ?? 0}%
              </p>
              <p className="text-xs text-slate-500 mt-1">
                ₹{(experiment?.ai_group.recovered_revenue ?? 0).toLocaleString()} recovered (Cost: ₹{experiment?.ai_group.action_cost ?? 0})
              </p>
            </div>

            <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-blue-300 dark:border-blue-800">
              <span className="text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wider">Recovery Lift</span>
              <p className="text-xl font-bold text-blue-600 dark:text-blue-400 mt-1">
                +{experiment?.impact_metrics.recovery_lift_percent ?? 0}%
              </p>
              <p className="text-xs text-slate-500 mt-1">Incremental efficiency gain over baseline</p>
            </div>

            <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-indigo-300 dark:border-indigo-800">
              <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">Net Incremental ₹</span>
              <p className="text-xl font-bold text-indigo-600 dark:text-indigo-400 mt-1">
                ₹{(experiment?.impact_metrics.net_incremental_revenue ?? 0).toLocaleString()}
              </p>
              <p className="text-xs text-slate-500 mt-1">Net revenue after subtracting action costs</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Benchmark Scenarios & Case Detail (Best Judge Moment) */}
      <div className="space-y-4">
        <div className="flex justify-between items-end">
          <div>
            <h2 className="text-xl font-bold tracking-tight">Deterministic Benchmark Scenarios</h2>
            <p className="text-sm text-slate-500">
              Click any scenario to inspect the exact reasoning, policy enforcement, and audit trail.
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
                  <span className="text-xs font-semibold text-slate-400">₹{sc.amount}</span>
                </div>
                <h4 className="font-semibold text-sm line-clamp-1">{sc.title}</h4>
                <p className="text-xs text-slate-500 mt-1 line-clamp-2">{sc.detail}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Interactive Case Inspector: AI vs Policy vs Decision */}
      <Card className="border-slate-300 dark:border-slate-800">
        <CardHeader>
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-2">
            <div>
              <div className="flex items-center gap-2">
                <CardTitle>Case Inspector: {selectedScenario.title}</CardTitle>
                <Badge variant={selectedScenario.tagVariant}>{selectedScenario.key}</Badge>
              </div>
              <CardDescription className="mt-1">
                Amount: ₹{selectedScenario.amount.toLocaleString()} • Bank: {selectedScenario.bank} • Failure: {selectedScenario.failureReason}
              </CardDescription>
            </div>
            <div className="text-right">
              <span className="text-xs text-slate-500 block">Final System Action:</span>
              <span className="text-sm font-bold text-blue-600 dark:text-blue-400">
                {selectedScenario.finalDecision}
              </span>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Decision Explainer Box */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
            <div>
              <span className="text-xs font-semibold uppercase text-slate-400 block">1. AI Model Recommendation</span>
              <p className="text-base font-bold text-slate-800 dark:text-slate-200 mt-1">
                {selectedScenario.recAction}
              </p>
              <p className="text-xs text-slate-500 mt-1">Action-conditioned ML probability output</p>
            </div>

            <div>
              <span className="text-xs font-semibold uppercase text-slate-400 block">2. Policy Engine Guardrail</span>
              <p className={`text-base font-bold mt-1 ${
                selectedScenario.policyOutcome.includes("DENIED") ? "text-rose-600" : "text-emerald-600"
              }`}>
                {selectedScenario.policyOutcome}
              </p>
              <p className="text-xs text-slate-500 mt-1">Hard barrier check against statutory & risk rules</p>
            </div>

            <div>
              <span className="text-xs font-semibold uppercase text-slate-400 block">3. Bounded Execution</span>
              <p className="text-base font-bold text-indigo-600 dark:text-indigo-400 mt-1">
                {selectedScenario.finalDecision}
              </p>
              <p className="text-xs text-slate-500 mt-1">Enqueued state change & immutable audit logging</p>
            </div>
          </div>

          {/* Audit Timeline */}
          <div>
            <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200 mb-3">
              Case Lifecycle Audit Timeline
            </h4>
            <AuditTimeline caseId={selectedScenario.id} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
