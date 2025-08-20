import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useApiKey } from './apiKey';

export default function RequireApiKey({
  children,
}: {
  children: JSX.Element;
}) {
  const { apiKey } = useApiKey();
  const location = useLocation();
  if (!apiKey) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return children;
}
