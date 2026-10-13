export { Logo } from "../brand/Logo";
import { Logo as BrandLogo } from "../brand/Logo";

/** @deprecated Use `<Logo variant="mark" />` */
export function LogoMark({ className = "" }: { className?: string }) {
  return <BrandLogo variant="mark" size={28} className={className} />;
}
