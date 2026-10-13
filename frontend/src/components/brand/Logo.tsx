import black1x from "../../assets/brand/aqrem-logo-black.png";
import black2x from "../../assets/brand/aqrem-logo-black@2x.png";
import black3x from "../../assets/brand/aqrem-logo-black@3x.png";
import white1x from "../../assets/brand/aqrem-logo-white.png";
import white2x from "../../assets/brand/aqrem-logo-white@2x.png";
import white3x from "../../assets/brand/aqrem-logo-white@3x.png";

/** Trimmed master aspect (width / height). */
const MARK_ASPECT = 1159 / 1106;

export type LogoVariant = "mark" | "full";

type Props = {
  variant?: LogoVariant;
  /** Mark height in px (default 28). */
  size?: number;
  className?: string;
  alt?: string;
};

function LogoMarkImage({ size, alt }: { size: number; alt: string }) {
  const width = Math.round(size * MARK_ASPECT);
  return (
    <span className="aq-logo-mark inline-flex shrink-0 items-center justify-center" style={{ width, height: size }}>
      <img
        src={black1x}
        srcSet={`${black1x} 1x, ${black2x} 2x, ${black3x} 3x`}
        width={width}
        height={size}
        alt={alt}
        className="aq-logo-img aq-logo-img--light h-full w-auto object-contain"
        decoding="sync"
      />
      <img
        src={white1x}
        srcSet={`${white1x} 1x, ${white2x} 2x, ${white3x} 3x`}
        width={width}
        height={size}
        alt=""
        aria-hidden
        className="aq-logo-img aq-logo-img--dark h-full w-auto object-contain"
        decoding="sync"
      />
    </span>
  );
}

export function Logo({ variant = "full", size = 28, className = "", alt }: Props) {
  const markAlt = alt ?? (variant === "full" ? "" : "AQREM");
  const wordmark = variant === "full" ? (
    <span className="aq-logo-wordmark text-[15px] font-semibold tracking-tight">AQREM</span>
  ) : null;

  return (
    <span className={`aq-logo inline-flex items-center gap-2.5 min-w-0 ${className}`}>
      <LogoMarkImage size={size} alt={markAlt} />
      {wordmark}
    </span>
  );
}
