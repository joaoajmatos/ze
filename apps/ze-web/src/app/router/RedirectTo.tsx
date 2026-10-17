import { Navigate, generatePath, useLocation, useParams } from "react-router-dom";

interface RedirectToProps {
  to: string;
  /** Replaces the incoming hash; loaders lose the hash, so the destination names its own target. */
  hint?: string;
  /** Incoming hashes that win over `hint`, for bookmarks that already name a target. */
  hintMap?: Record<string, string>;
}

/** Sends an old path to its place, keeping params and query; the hash passes through unless the entry has a hint. */
export function RedirectTo({ to, hint, hintMap }: RedirectToProps) {
  const params = useParams();
  const { search, hash } = useLocation();
  const incoming = hash.replace(/^#/, "");
  const target = hint === undefined ? hash : `#${hintMap?.[incoming] ?? hint}`;
  return <Navigate replace to={`${generatePath(to, params)}${search}${target}`} />;
}
