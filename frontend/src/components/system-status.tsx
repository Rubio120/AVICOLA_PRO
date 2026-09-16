type SystemStatusProps = {
  available: boolean;
};

export function SystemStatus({ available }: SystemStatusProps) {
  return (
    <div className={`status ${available ? "status--ready" : "status--degraded"}`} role="status">
      <span aria-hidden="true" className="status__indicator" />
      <span>{available ? "API y base de datos disponibles" : "API o base de datos no disponibles"}</span>
    </div>
  );
}

