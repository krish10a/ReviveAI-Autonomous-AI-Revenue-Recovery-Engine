"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useState } from "react";

const BatchSimulator: React.FC = () => {
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState({
    totalInjected: 0,
    diagnosed: 0,
    actionsChosen: 0,
    executed: 0,
    verified: 0,
    amountRecovered: 0
  });
  const [logs, setLogs] = useState<string[]>([]);

  const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, `[${timestamp}] ${message}`]);
    // Keep only last 50 logs
    if (logs.length > 50) {
      setLogs(prev => prev.slice(-50));
    }
  };

  const runSimulation = async () => {
    setIsRunning(true);
    setProgress(0);
    addLog("Starting batch simulation...");

    try {
      // Call the backend batch simulation endpoint
      const response = await fetch("/api/simulate/batch", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ total_cases: 100 })
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch: ${response.status}`);
      }

      const data = await response.json();

      // Update results with real data from backend
      setResults(data.results || {
        totalInjected: 0,
        diagnosed: 0,
        actionsChosen: 0,
        executed: 0,
        verified: 0,
        amountRecovered: 0
      });

      // Add logs from backend response
      if (data.logs) {
        data.logs.forEach((log: string) => addLog(log));
      }

      addLog(`Batch simulation complete! Recovered ₹{results.amountRecovered.toLocaleString()} from ${results.verified}/${results.totalInjected} cases.`);
    } catch (err) {
      addLog(`Error running simulation: ${err instanceof Error ? err.message : "Unknown error"}`);
      console.error("Error running batch simulation:", err);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Batch Simulator</CardTitle>
        <CardDescription>
          Inject synthetic failed payments to demo the end-to-end recovery flow
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Controls */}
          <div className="flex items-center space-x-3">
            <Button 
              onClick={runSimulation}
              disabled={isRunning}
              className="w-48"
            >
              {isRunning ? "Running..." : "Run Batch Simulation"}
            </Button>
            
            <div className="flex-1">
              <div className="w-full bg-gray-200 rounded-full h-2.5">
                <div 
                  className="bg-primary h-2.5 rounded-full" 
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {progress}% complete
              </p>
            </div>
          </div>
          
          {/* Results */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <p className="text-muted-foreground text-sm">Total Injected</p>
              <p className="text-2xl font-bold">{results.totalInjected}</p>
            </div>
            
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <p className="text-muted-foreground text-sm">Diagnosed</p>
              <p className="text-2xl font-bold">{results.diagnosed}</p>
            </div>
            
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <p className="text-muted-foreground text-sm">Actions Chosen</p>
              <p className="text-2xl font-bold">{results.actionsChosen}</p>
            </div>
            
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <p className="text-muted-foreground text-sm">Executed</p>
              <p className="text-2xl font-bold">{results.executed}</p>
            </div>
            
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <p className="text-muted-foreground text-sm">Verified Recovered</p>
              <p className="text-2xl font-bold">{results.verified}</p>
            </div>
            
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <p className="text-muted-foreground text-sm">Amount Recovered</p>
              <p className="text-2xl font-bold">₹{results.amountRecovered.toLocaleString()}</p>
            </div>
          </div>
          
          {/* Recovery Rate */}
          <div className="text-center py-4 border-t">
            {results.totalInjected > 0 && (
              <div className="space-y-2">
                <p className="text-muted-foreground text-sm">Recovery Rate</p>
                <p className="text-2xl font-bold text-primary">
                  {((results.verified / results.totalInjected) * 100).toFixed(1)}%
                </p>
              </div>
            )}
          </div>
          
          {/* Logs */}
          <div className="mt-4">
            <div className="flex justify-between">
              <h3 className="font-medium">Simulation Log</h3>
              <Button 
                variant="outline"
                size="sm"
                onClick={() => setLogs([])}
              >
                Clear Log
              </Button>
            </div>
            <div className="mt-2 h-40 w-full overflow-y-auto text-xs font-mono bg-gray-50 rounded-lg p-3">
              {logs.map((log, index) => (
                <div key={index} className="mb-1">{log}</div>
              ))}
              {logs.length === 0 && (
                <p className="text-muted-foreground italic">No logs yet. Run a simulation to see activity.</p>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default BatchSimulator;
