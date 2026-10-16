import type { WsConfirmRequestFrame } from "@myguyze/ze-client";

export type ConfirmItem = WsConfirmRequestFrame["items"][number];
export type ConfirmSource = NonNullable<WsConfirmRequestFrame["source"]>;
