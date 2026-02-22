import styles from "./SetiIcon.module.css";
import clsx from "clsx";

type SetiIconProps = {
  svg: string;
  size?: number;
  className?: string;
};

export function SetiIcon({ svg, size = 16, className }: SetiIconProps) {
  return (
    <span
      className={clsx(styles.icon, className)}
      style={{ width: size, height: size }}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
