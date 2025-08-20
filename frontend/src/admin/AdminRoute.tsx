import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import useAuth from '../hooks/useAuth';

export default function AdminRoute({ children }: { children: JSX.Element }) {
  const { roles } = useAuth();
  const navigate = useNavigate();
  const isAdmin = roles.includes('admin');

  useEffect(() => {
    if (!isAdmin) {
      toast.error('You are not authorized to view this page');
      navigate('/', { replace: true });
    }
  }, [isAdmin, navigate]);

  return isAdmin ? children : null;
}
