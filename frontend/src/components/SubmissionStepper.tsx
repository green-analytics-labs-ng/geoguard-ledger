import type { SubmissionStep } from "../types";

interface Props {
  currentStep: SubmissionStep;
}

const STEPS: { key: SubmissionStep; label: string }[] = [
  { key: "upload", label: "Upload" },
  { key: "preview", label: "Preview" },
  { key: "ai-report", label: "AI Report" },
  { key: "sign", label: "Sign" },
  { key: "confirmed", label: "Confirmed" },
];

const STEP_INDEX: Record<SubmissionStep, number> = {
  upload: 0,
  preview: 1,
  "ai-report": 2,
  sign: 3,
  confirmed: 4,
};

export default function SubmissionStepper({ currentStep }: Props) {
  const currentIndex = STEP_INDEX[currentStep];

  return (
    <div className="flex items-center justify-center gap-0">
      {STEPS.map((step, i) => {
        const isCompleted = i < currentIndex;
        const isCurrent = i === currentIndex;

        return (
          <div key={step.key} className="flex items-center">
            {/* Step circle + label */}
            <div className="flex flex-col items-center">
              <div
                className={`
                  w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium
                  transition-all duration-300
                  ${
                    isCompleted
                      ? "bg-green-500 text-white"
                      : isCurrent
                        ? "bg-stellar text-white ring-4 ring-blue-100"
                        : "bg-gray-200 text-gray-500"
                  }
                `}
              >
                {isCompleted ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  i + 1
                )}
              </div>
              <span
                className={`mt-1 text-xs ${
                  isCurrent ? "text-stellar font-medium" : "text-gray-500"
                }`}
              >
                {step.label}
              </span>
            </div>

            {/* Connector line */}
            {i < STEPS.length - 1 && (
              <div className="w-12 md:w-20 h-0.5 mx-2 relative">
                <div className="absolute inset-0 bg-gray-200 rounded" />
                <div
                  className={`absolute inset-y-0 left-0 bg-green-500 rounded transition-all duration-500 ${
                    i < currentIndex ? "w-full" : "w-0"
                  }`}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
