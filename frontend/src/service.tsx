import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { DEFAULT_LIMITS, getServiceInfo, type Limits } from "./api/client";
import TERMS_VERSION_FILE from "../../legal/VERSION?raw";

/** Date of the Terms and Conditions this interface shows (legal/VERSION). */
export const TERMS_VERSION = TERMS_VERSION_FILE.trim();

interface Service {
  readonly limits: Limits;
  readonly version: string | undefined;
}

const ServiceContext = createContext<Service>({ limits: DEFAULT_LIMITS, version: undefined });

/** The deployment's limits, from GET /api/v1/info; the defaults until it answers. */
export function ServiceProvider({ children }: { children: ReactNode }) {
  const [service, setService] = useState<Service>({ limits: DEFAULT_LIMITS, version: undefined });
  useEffect(() => {
    const controller = new AbortController();
    getServiceInfo(controller.signal).then(
      (info) => setService({ limits: info.limits, version: info.version }),
      () => undefined,
    );
    return () => controller.abort();
  }, []);
  return <ServiceContext.Provider value={service}>{children}</ServiceContext.Provider>;
}

export function useService(): Service {
  return useContext(ServiceContext);
}
