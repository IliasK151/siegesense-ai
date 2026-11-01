import type { Profile, StatusPayload } from "@shared/protocol";
import type { ReactNode } from "react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { EngineState, SiegeSenseApi } from "../../../preload/api";
import { type ConnState, type EngineConnection, EngineClient } from "./engineClient";

export type EngineLike = Pick<EngineClient, "connect" | "request" | "on" | "onState" | "close" | "connState">;
type ProfileState = { profile: Profile | null; loading: boolean; reload: () => Promise<void> };

type Ctx = {
  client: EngineLike;
  connState: ConnState;
  engineState: EngineState | null;
  status: StatusPayload | null;
  profile: ProfileState;
};

const EngineCtx = createContext<Ctx | null>(null);

/** In Electron the preload bridge gives us the engine; in a plain browser (e2e) use URL params. */
function browserConnection(): Promise<EngineConnection> {
  const params = new URLSearchParams(window.location.search);
  const port = Number(params.get("port"));
  const token = params.get("token") ?? "";
  return port ? Promise.resolve({ port, token }) : new Promise(() => {});
}

function defaultClient(): EngineLike {
  return new EngineClient(() => window.siegesense?.getEngine() ?? browserConnection());
}

type Props = {
  children: ReactNode;
  client?: EngineLike;
  onEngineState?: SiegeSenseApi["onEngineState"];
};

export function EngineProvider({ children, client: injected, onEngineState }: Props) {
  const client = useMemo(() => injected ?? defaultClient(), [injected]);
  const [connState, setConnState] = useState<ConnState>(client.connState);
  const [engineState, setEngineState] = useState<EngineState | null>(null);
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    const res = await client.request<{ profile: Profile | null }>("get_profile");
    setProfile(res.profile);
    setLoading(false);
  }, [client]);

  useEffect(() => {
    const subscribe = onEngineState ?? window.siegesense?.onEngineState;
    return subscribe?.(setEngineState);
  }, [onEngineState]);

  useEffect(() => {
    const offStatus = client.on("status", setStatus);
    const refresh = () => {
      reload().catch(() => {});
      client
        .request<StatusPayload>("get_status")
        .then(setStatus)
        .catch(() => {});
    };
    const offState = client.onState((s) => {
      setConnState(s);
      if (s === "open") refresh();
    });
    client
      .connect()
      .then(() => {
        setConnState(client.connState);
        refresh();
      })
      .catch(() => {});
    return () => {
      offStatus();
      offState();
    };
  }, [client, reload]);

  const value = useMemo<Ctx>(
    () => ({ client, connState, engineState, status, profile: { profile, loading, reload } }),
    [client, connState, engineState, status, profile, loading, reload],
  );
  return <EngineCtx.Provider value={value}>{children}</EngineCtx.Provider>;
}

function useCtx(): Ctx {
  const ctx = useContext(EngineCtx);
  if (!ctx) throw new Error("EngineProvider is missing");
  return ctx;
}

export const useEngine = () => useCtx().client;
export const useConnState = () => useCtx().connState;
export const useEngineState = () => useCtx().engineState;
export const useStatus = () => useCtx().status;
export const useProfile = () => useCtx().profile;
