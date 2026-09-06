"use client";

import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Clock,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Cpu,
  Lock,
  Zap,
  Activity
} from "lucide-react";

interface TimelineEvent {
  id: number;
  timestamp: string;
  actor: string;
  action: string;
  input_json?: string | null;
  decision_json?: string | null;
}

interface AuditTimelineProps {
  caseId?: number;
  scenarioKey?: string;
}

export default function AuditTimeline({ caseId, scenarioKey }: AuditTimelineProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [activeWhyId, setActiveWhyId] = useState<number | null>(null);

  useEffect(() => {
    const fetchTimeline = async () => {
      try {
        setLoading(true);
        const endpoint = scenarioKey
          ? `/api/timeline/scenario/${scenarioKey}`
          : `/api/timeline/case/${caseId}`;
        const res = await fetch(endpoint);
        if (res.ok) {
          const data: TimelineEvent[] = await res.json();
          setEvents(data);
          // Expand the policy decision event by default for fast inspection
          const policyEvt = data.find(e => e.action.includes("POLICY") || (e.decision_json && e.decision_json.includes("denied")));
          if (policyEvt) {
            setExpandedId(policyEvt.id);
          }
        } else {
          setEvents([]);
        }
      } catch (err) {
        console.error("Timeline load failed:", err);
        setEvents([]);
      } finally {
        setLoading(false);
      }
    };

    if (scenarioKey || caseId) {
      fetchTimeline();
    }
  }, [caseId, scenarioKey]);

  if (loading) {
    return <div className="text-xs text-slate-500 py-4 animate-pulse">Loading audit trail...</div>;
  }

  if (!events || events.length === 0) {
    return (
      <div className="text-xs text-slate-400 py-3 italic border border-dashed rounded-lg p-4 text-center">
        Zero mutations or policy overrides pending for this case.
      </div>
    );
  }

  const getLifecycleBadge = (action: string, isDenied: boolean, isAllowed: boolean) => {
    const actUpper = action.toUpperCase();
    if (actUpper.includes("DIAGNOSE")) {
      return <Badge variant="outline" className="text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">DIAGNOSIS</Badge>;
    }
    if (actUpper.includes("PREDICT")) {
      return <Badge variant="default" className="text-[10px] bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300">PROPOSAL</Badge>;
    }
    if (actUpper.includes("POLICY")) {
      return isDenied ? (
        <Badge variant="destructive" className="text-[10px]">POLICY BLOCKED</Badge>
      ) : (
        <Badge variant="success" className="text-[10px]">POLICY APPROVED</Badge>
      );
    }
    if (actUpper.includes("EXECUTE")) {
      if (actUpper.includes("STOP")) return <Badge variant="destructive" className="text-[10px]">STOP ENFORCED</Badge>;
      if (actUpper.includes("WAIT")) return <Badge variant="warning" className="text-[10px]">WAIT DEFERRED</Badge>;
      if (actUpper.includes("ESCALATE")) return <Badge variant="default" className="text-[10px]">ESCALATED</Badge>;
      return <Badge variant="default" className="text-[10px] bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300">EXECUTED</Badge>;
    }
    if (actUpper.includes("VERIFY")) {
      if (actUpper.includes("ESCALAT") || actUpper.includes("PENDING")) {
        return <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-300 dark:text-amber-400 dark:border-amber-700">PENDING HUMAN RESOLUTION</Badge>;
      }
      if (actUpper.includes("CUSTOMER_PROTECTED") || actUpper.includes("PROTECT")) {
        return <Badge variant="outline" className="text-[10px] text-indigo-600 border-indigo-300 dark:text-indigo-400 dark:border-indigo-700">CUSTOMER PROTECTED</Badge>;
      }
      if (actUpper.includes("DEFERRED") || actUpper.includes("WAIT")) {
        return <Badge variant="warning" className="text-[10px]">DEFERRED</Badge>;
      }
      if (actUpper.includes("UNRESOLVED")) {
        return <Badge variant="outline" className="text-[10px] text-slate-500">UNRESOLVED</Badge>;
      }
      return <Badge variant="success" className="text-[10px]">INDEPENDENT VERIFIED</Badge>;
    }
    return <Badge variant="outline" className="text-[10px]">AUDIT</Badge>;
  };

  const getMarkerIcon = (action: string, isDenied: boolean) => {
    const actUpper = action.toUpperCase();
    if (isDenied) return <ShieldAlert className="w-3.5 h-3.5 text-rose-500" />;
    if (actUpper.includes("POLICY")) return <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />;
    if (actUpper.includes("PREDICT")) return <Cpu className="w-3.5 h-3.5 text-blue-500" />;
    if (actUpper.includes("VERIFY")) return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />;
    if (actUpper.includes("EXECUTE")) return <Zap className="w-3.5 h-3.5 text-indigo-500" />;
    return <Activity className="w-3.5 h-3.5 text-slate-400" />;
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs text-slate-500 pb-1 border-b border-slate-200 dark:border-slate-800">
        <span>Click any event to inspect full JSON payload and policy reasoning.</span>
        <span>{events.length} lifecycle events</span>
      </div>

      <div className="relative pl-6 space-y-3 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200 dark:before:bg-slate-800">
        {events.map((evt) => {
          interface DecisionObj {
            result?: string;
            denied?: boolean;
            allowed?: boolean;
            reason?: string;
            rule_violations?: string[];
            action_type?: string;
            raw?: string | null;
            [key: string]: any;
          }

          let decObj: DecisionObj | null = null;
          let inObj: any = null;

          try {
            if (evt.decision_json) {
              decObj = typeof evt.decision_json === "string" ? JSON.parse(evt.decision_json) : evt.decision_json;
            }
          } catch {
            decObj = { raw: evt.decision_json };
          }

          try {
            if (evt.input_json) {
              inObj = typeof evt.input_json === "string" ? JSON.parse(evt.input_json) : evt.input_json;
            }
          } catch {
            inObj = { raw: evt.input_json };
          }

          const isDenied = decObj?.result === "DENIED" || decObj?.denied === true;
          const isAllowed = decObj?.result === "ALLOWED" || decObj?.allowed === true;
          const isPolicyEvent = evt.action.toUpperCase().includes("POLICY") || Boolean(decObj?.rule_violations) || isDenied;

          const timeStr = evt.timestamp ? (() => {
            try {
              const d = new Date(evt.timestamp);
              return isNaN(d.getTime()) ? String(evt.timestamp) : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
            } catch {
              return String(evt.timestamp);
            }
          })() : "";

          const isExpanded = expandedId === evt.id;
          const isWhyActive = activeWhyId === evt.id;

          return (
            <div key={evt.id} className="relative group">
              {/* Timeline marker icon */}
              <div className={`absolute -left-6 top-1 w-5 h-5 rounded-full flex items-center justify-center bg-white dark:bg-slate-900 border ${
                isDenied ? "border-rose-500 shadow-rose-200 shadow-sm" : isPolicyEvent ? "border-emerald-500 shadow-sm" : "border-slate-300 dark:border-slate-700"
              }`}>
                {getMarkerIcon(evt.action, isDenied)}
              </div>

              {/* Event Card (Clickable to Expand) */}
              <div
                onClick={() => setExpandedId(isExpanded ? null : evt.id)}
                className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
                  isExpanded
                    ? "border-blue-400 bg-white dark:bg-slate-900 shadow-md ring-1 ring-blue-400/30"
                    : isDenied
                      ? "border-rose-200 bg-rose-50/30 dark:border-rose-900/40 dark:bg-rose-950/20 hover:border-rose-300"
                      : "border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/50 hover:border-slate-300 dark:hover:border-slate-700"
                }`}
              >
                {/* Header Row */}
                <div className="flex flex-wrap justify-between items-center gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-semibold text-slate-800 dark:text-slate-200">
                      {evt.action}
                    </span>
                    {getLifecycleBadge(evt.action, isDenied, isAllowed)}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-slate-400 flex items-center gap-1 font-mono">
                      <Clock className="w-3 h-3" /> {timeStr}
                    </span>
                    {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                  </div>
                </div>

                {/* Sub-label showing Actor */}
                <div className="text-[11px] text-slate-500 mt-1 flex items-center gap-1.5">
                  <span className="font-semibold text-slate-600 dark:text-slate-400">Actor:</span>
                  <code className="bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded text-[10px]">{evt.actor}</code>
                </div>

                {/* Summary Reason Preview */}
                {decObj?.reason && (
                  <p className={`text-xs mt-2 font-medium ${isDenied ? "text-rose-600 dark:text-rose-400" : "text-slate-700 dark:text-slate-300"}`}>
                    {decObj.reason}
                  </p>
                )}

                {/* Violations preview if any */}
                {Array.isArray(decObj?.rule_violations) && decObj.rule_violations.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {decObj.rule_violations.map((v: string) => (
                      <Badge key={v} variant="destructive" className="text-[10px] py-0 px-2 font-mono">
                        Violation: {v}
                      </Badge>
                    ))}
                  </div>
                )}

                {/* "Why?" Button for Policy Reason Insight */}
                {isPolicyEvent && (
                  <div className="mt-2.5 pt-2 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveWhyId(isWhyActive ? null : evt.id);
                      }}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      <HelpCircle className="w-3.5 h-3.5" />
                      {isWhyActive ? "Hide Policy Reasoning" : "Why did Policy choose this?"}
                    </button>
                    {isDenied && (
                      <span className="text-[10px] uppercase font-bold text-rose-600 tracking-wider">
                        Guardrail Enforced
                      </span>
                    )}
                  </div>
                )}

                {/* Expanded "Why?" Policy Reasoning Box */}
                {isWhyActive && (
                  <div className="mt-3 p-3 rounded-lg bg-blue-50/70 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900 text-xs space-y-1.5" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center gap-1.5 font-bold text-blue-900 dark:text-blue-200">
                      <Lock className="w-3.5 h-3.5 text-blue-600" />
                      Deterministic Policy Engine Rationale
                    </div>
                    <p className="text-slate-700 dark:text-slate-300">
                      <strong>Decision:</strong> {isDenied ? "REJECTED proposed action" : "APPROVED action"}
                    </p>
                    <p className="text-slate-700 dark:text-slate-300">
                      <strong>Guardrail Rule:</strong> {decObj?.rule_violations?.join(", ") || decObj?.reason || "Statutory & Risk Safety Check"}
                    </p>
                    <p className="text-slate-600 dark:text-slate-400 text-[11px]">
                      <strong>Enforcement Principle:</strong> AI models generate probability proposals; deterministic code guardrails enforce invariant safety barriers before execution.
                    </p>
                  </div>
                )}

                {/* Expanded Full JSON Inspector */}
                {isExpanded && (
                  <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-800 space-y-2 text-xs" onClick={(e) => e.stopPropagation()}>
                    {inObj && (
                      <div>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                          Input Parameters:
                        </span>
                        <pre className="p-2 rounded bg-slate-100 dark:bg-slate-950 text-[11px] font-mono overflow-x-auto text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-800">
                          {JSON.stringify(inObj, null, 2)}
                        </pre>
                      </div>
                    )}
                    {decObj && (
                      <div>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                          Decision / Output Payload:
                        </span>
                        <pre className="p-2 rounded bg-slate-100 dark:bg-slate-950 text-[11px] font-mono overflow-x-auto text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-800">
                          {JSON.stringify(decObj, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}