import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function Icon({ children, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

export const LogoMark = (props: IconProps) => (
  <svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true" focusable="false" {...props}>
    <path d="M8 2h11l7 7v19a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="var(--accent)" />
    <path d="M19 2v5a2 2 0 0 0 2 2h5" fill="var(--accent-soft-strong)" />
    <path d="M11 16h10M11 20h10M11 24h6" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

export const UploadIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M12 16V4M7 9l5-5 5 5" />
    <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
  </Icon>
);

export const MergeIcon = (props: IconProps) => (
  <Icon {...props}>
    <rect x="3" y="3" width="8" height="10" rx="1" />
    <rect x="13" y="3" width="8" height="10" rx="1" />
    <path d="M7 13v3a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-3M12 18v3" />
  </Icon>
);

export const SplitIcon = (props: IconProps) => (
  <Icon {...props}>
    <circle cx="6" cy="6" r="3" />
    <circle cx="6" cy="18" r="3" />
    <path d="M20 4 8.1 15.9M14.5 14.5 20 20M8.1 8.1 12 12" />
  </Icon>
);

export const RotateIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
    <path d="M21 3v5h-5" />
  </Icon>
);

export const RotateLeftIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
    <path d="M3 3v5h5" />
  </Icon>
);

export const CloseIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M18 6 6 18M6 6l12 12" />
  </Icon>
);

export const GripIcon = (props: IconProps) => (
  <Icon {...props} strokeWidth="3">
    <path d="M9 6h.01M15 6h.01M9 12h.01M15 12h.01M9 18h.01M15 18h.01" />
  </Icon>
);

export const FileIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" />
  </Icon>
);

export const CheckIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M20 6 9 17l-5-5" />
  </Icon>
);

export const AlertIcon = (props: IconProps) => (
  <Icon {...props}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v5M12 16h.01" />
  </Icon>
);

export const LockIcon = (props: IconProps) => (
  <Icon {...props}>
    <rect x="4" y="11" width="16" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </Icon>
);

export const SortIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M3 6h10M3 12h7M3 18h4M17 4v16M14 17l3 3 3-3" />
  </Icon>
);

export const SwapIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M7 4v16M4 7l3-3 3 3M17 20V4M14 17l3 3 3-3" />
  </Icon>
);
