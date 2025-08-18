import { useConfig } from '../config';

export default function Footer() {
  const { POWERED_BY_LABEL } = useConfig();
  return <footer>{POWERED_BY_LABEL}</footer>;
}
