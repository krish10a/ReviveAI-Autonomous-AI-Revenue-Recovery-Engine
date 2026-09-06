"use client";

import { useState, useEffect } from "react";

import { Badge } from "@/components/ui/badge";
import { Clock, ShieldAlert, CheckCircle2, ArrowRight } from "lucide-react";

interface TimelineEvent {
  id: number;
  timestamp: string;
  actor: string;
  action: string;
  input_json?: string | null;
  decision_json?: string | null;
}

interface AuditTimelineProps {
  caseId: number;
}

export default function AuditTimeline({ caseId }: AuditTimelineProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTimeline = async () => {
      try {
        setLoading(true);
        const res = await fetch(`/api/timeline/case/${caseId}`);
        if (res.ok) {
          const data: TimelineEvent[] = await res.json();
          setEvents(data);
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

    if (caseId) {
      fetchTimeline();
    }
  }, [caseId]);

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

  return (
    <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200 dark:before:bg-slate-800">
      {events.map((evt) => {
        interface DecisionObj {
          result?: string;
          denied?: boolean;
          reason?: string;
          rule_violations?: string[];
          raw?: string | null;
        }
        let decObj: DecisionObj | null = null;
        try {
          if (evt.decision_json) {
            decObj = typeof evt.decision_json === "string" ? JSON.parse(evt.decision_json) : evt.decision_json;
          }
        } catch {
          decObj = { raw: evt.decision_json };
        }

        const isDenied = decObj?.result === "DENIED" || decObj?.denied;
        const timeStr = evt.timestamp ? (() => {
          try {
            const d = new Date(evt.timestamp);
            return isNaN(d.getTime()) ? String(evt.timestamp) : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
          } catch {
            return String(evt.timestamp);
          }
        })() : "";

        return (
          <div key={evt.id} className="relative group">
            {/* Timeline marker icon */}
            <div className={`absolute -left-6 top-0.5 w-5 h-5 rounded-full flex items-center justify-center text-white text-[10px] ${
              isDenied ? "bg-rose-500" : "bg-blue-600"
            }`}>
              {isDenied ? <ShieldAlert className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
            </div>

            <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <div className="flex justify-between items-center mb-1">
                <span className="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                  {evt.actor} <ArrowRight className="w-3 h-3 text-slate-400" /> {evt.action}
                </span>
                <span className="text-[10px] text-slate-400 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> {timeStr}
                </span>
              </div>

              {decObj && (
                <div className="text-xs text-slate-600 dark:text-slate-400 mt-1.5">
                  {decObj.reason && (
                    <p className={`font-medium ${isDenied ? "text-rose-600 dark:text-rose-400" : "text-slate-700 dark:text-slate-300"}`}>
                      {decObj.reason}
                    </p>
                  )}
                  {Array.isArray(decObj.rule_violations) && decObj.rule_violations.length > 0 && (
                    <div className="flex gap-1 mt-1">
                      {decObj.rule_violations.map((v: string) => (
                        <Badge key={v} variant="destructive" className="text-[10px] py-0 px-1.5">
                          {v}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}