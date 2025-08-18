import { useConfig } from '../config';

export default function Header() {
  const { BRAND_NAME, LOGO_URL } = useConfig();
  return (
    <header>
      {LOGO_URL && <img src={LOGO_URL} alt={BRAND_NAME} className="logo" />}
      <h1>{BRAND_NAME}</h1>
    </header>
  );
}
