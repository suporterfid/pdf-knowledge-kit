import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import useAuth from '../hooks/useAuth';

export default function AdminRoute({ children }: { children: JSX.Element }) {
  const { roles, loading } = useAuth();
  const navigate = useNavigate();
  const hasAccess = roles.length > 0;

  useEffect(() => {
    if (!loading && !hasAccess) {
      toast.error('You are not authorized to view this page');
      navigate('/', { replace: true });
    }
  }, [loading, hasAccess, navigate]);

  return !loading && hasAccess ? children : null;
}
