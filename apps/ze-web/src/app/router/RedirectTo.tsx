import { Navigate, generatePath, useLocation, useParams } from "react-router-dom";

/** Sends an old path to its place, keeping params, query and hash (loaders lose the hash). */
export function RedirectTo({ to }: { to: string }) {
  const params = useParams();
  const { search, hash } = useLocation();
  return <Navigate replace to={`${generatePath(to, params)}${search}${hash}`} />;
}
