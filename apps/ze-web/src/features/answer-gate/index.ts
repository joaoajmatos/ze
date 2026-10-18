export { useAnswerGate } from "./api/useAnswerGate";
export { AnswerGateFrameHandler } from "./ui/AnswerGateFrameHandler";
export type { GateState } from "./api/useAnswerGate";
export type AnswerGate = ReturnType<typeof import("./api/useAnswerGate").useAnswerGate>;
