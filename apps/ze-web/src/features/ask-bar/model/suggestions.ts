export type SuggestionLanguage = "en" | "pt";

/** Three questions worth asking about a thing, by kind. The first matching group wins; "default" covers the rest. */
const TABLE: Record<SuggestionLanguage, Record<string, [string, string, string]>> = {
  en: {
    workflow_execution: ["Why did this run end this way?", "What changed since the last run?", "What should I do about it?"],
    workflow: ["How is this workflow doing?", "What would you change in it?", "When does it run next?"],
    goal: ["How is this goal going?", "What is blocking it?", "What should I do next on it?"],
    goal_gate: ["What is this gate waiting for?", "Should I approve it?", "What happens if I don't?"],
    loop: ["Why is this open?", "Is this still worth keeping?", "What would close it?"],
    entity: ["What do you know about this?", "How is it connected to my other work?", "Is any of it out of date?"],
    fact: ["Why do you believe this?", "Is this still true?", "Where did it come from?"],
    default: ["What is the story here?", "What should I do about this?", "Why is it in this state?"],
  },
  pt: {
    workflow_execution: ["Porque é que esta execução terminou assim?", "O que mudou desde a última execução?", "O que devo fazer?"],
    workflow: ["Como está este fluxo de trabalho?", "O que mudarias nele?", "Quando corre a seguir?"],
    goal: ["Como está a correr este objetivo?", "O que o está a bloquear?", "O que devo fazer a seguir?"],
    goal_gate: ["Pelo que está esta verificação à espera?", "Devo aprová-la?", "O que acontece se não aprovar?"],
    loop: ["Porque é que isto está em aberto?", "Ainda vale a pena manter isto?", "O que o fecharia?"],
    entity: ["O que sabes sobre isto?", "Como se liga ao meu outro trabalho?", "Alguma parte está desatualizada?"],
    fact: ["Porque acreditas nisto?", "Isto ainda é verdade?", "De onde veio?"],
    default: ["Qual é a história aqui?", "O que devo fazer em relação a isto?", "Porque está neste estado?"],
  },
};

export function suggestionLanguage(): SuggestionLanguage {
  const lang = (typeof document !== "undefined" && document.documentElement.lang) || (typeof navigator !== "undefined" ? navigator.language : "") || "en";
  return lang.toLowerCase().startsWith("pt") ? "pt" : "en";
}

export function suggestionsFor(kind: string, language: SuggestionLanguage = suggestionLanguage()): string[] {
  const group = TABLE[language];
  return [...(group[kind] ?? group.default)];
}
