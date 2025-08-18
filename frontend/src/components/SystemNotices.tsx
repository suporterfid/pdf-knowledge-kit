interface Props {
  notices: any;
}

export default function SystemNotices({ notices }: Props) {
  if (!notices) return null;
  return (
    <div className="system-notices">
      <pre>{JSON.stringify(notices, null, 2)}</pre>
    </div>
  );
}
