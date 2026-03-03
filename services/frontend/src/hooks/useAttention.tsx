"use client";

import { createContext, useContext } from "react";

type AttentionContextType = {
  attentionRoomIds: Set<string>;
  adminNeedsAttention: boolean;
};

const AttentionContext = createContext<AttentionContextType>({
  attentionRoomIds: new Set(),
  adminNeedsAttention: false,
});

export const AttentionProvider = AttentionContext.Provider;

export function useAttention() {
  return useContext(AttentionContext);
}
