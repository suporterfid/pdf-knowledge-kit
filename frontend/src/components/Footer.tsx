import { useConfig } from '../config';

export default function Footer() {
  const { POWERED_BY_LABEL } = useConfig();
  return (
    <footer>
      <p>
        Este conteúdo é confidencial. Consulte os{' '}
        <a href="/terms" target="_blank" rel="noopener noreferrer">
          Termos de Uso
        </a>{' '}
        e a{' '}
        <a href="/privacy" target="_blank" rel="noopener noreferrer">
          Política de Privacidade
        </a>
        .
      </p>
      <span>{POWERED_BY_LABEL}</span>
    </footer>
  );
}
