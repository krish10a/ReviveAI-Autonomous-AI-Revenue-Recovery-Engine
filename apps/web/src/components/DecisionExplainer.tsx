"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { Button } from "@/components/ui/button";
import { useState } from "react";

const DecisionExplainer: React.FC<{ 
  caseId: number; 
  amount: number; 
  failureReason: string; 
  recoveryProbability: number; 
  expectedRecovery: number; 
  recommendedAction: string; 
}> = ({ caseId, amount, failureReason, recoveryProbability, expectedRecovery, recommendedAction }) => {
  const [tab, setTab] = useState<'summary' | 'details'>('summary');

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>AI Decision Explainer</CardTitle>
        <p className="text-muted-foreground">
          Understanding the recommendation for Case #{caseId}
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="flex justify-between pb-2 border-b">
            <button 
              className={`px-3 py-1 ${
                tab === 'summary' 
                  ? 'border-b-2 border-primary font-medium' 
                  : 'text-muted-foreground hover:text-foreground'
              }`}
              onClick={() => setTab('summary')}
            >
              Summary
            </button>
            <button 
              className={`px-3 py-1 ${
                tab === 'details' 
                  ? 'border-b-2 border-primary font-medium' 
                  : 'text-muted-foreground hover:text-foreground'
              }`}
              onClick={() => setTab('details')}
            >
              Details
            </button>
          </div>
          
          {tab === 'summary' && (
            <div className="space-y-3">
              <div className="flex items-start space-x-3">
                <span className="text-muted-foreground flex-shrink-0">Failure Reason:</span>
                <span>{failureReason}</span>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-muted-foreground flex-shrink-0">Recovery Probability:</span>
                <span className="font-medium">{Math.round(recoveryProbability * 100)}%</span>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-muted-foreground flex-shrink-0">Expected Recovery:</span>
                <span className="font-medium">₹{expectedRecovery.toLocaleString()}</span>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-muted-foreground flex-shrink-0">Recommended Action:</span>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  recommendedAction.includes('Escalate') 
                    ? 'bg-red-100 text-red-800'
                    : recommendedAction.includes('Payment Link')
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-green-100 text-green-800'
                }`}>
                  {recommendedAction}
                </span>
              </div>
            </div>
          )}
          
          {tab === 'details' && (
            <div className="space-y-3">
              <div className="border-t pt-4">
                <h3 className="font-medium mb-2">How the Decision Was Made</h3>
                <p className="text-sm text-muted-foreground">
                  The AI analyzed the payment failure ({failureReason}) and calculated the expected 
                  value for each possible recovery action. The recommended action ({recommendedAction}) 
                  was selected because it offers the highest expected value while complying with 
                  all business rules and regulatory requirements.
                </p>
              </div>
              
              <div className="border-t pt-4">
                <h3 className="font-medium mb-2">Expected Value Calculation</h3>
                <p className="text-sm text-muted-foreground">
                  Expected Value = (Probability of Success × Amount) − Cost of Action
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  For {recommendedAction}: ({Math.round(recoveryProbability * 100)}% × ₹{amount.toLocaleString()}) − Cost 
                  = ₹{expectedRecovery.toLocaleString()}
                </p>
              </div>
            </div>
          )}
        </div>
        
        <div className="mt-4 pt-3 border-t">
          <Button 
            variant="outline"
            onClick={() => console.log('Execute action clicked')}
            className="w-full"
          >
            Execute {recommendedAction}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default DecisionExplainer;
