import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import ChatPage from './ChatPage';
import AdminApp from './admin/AdminApp';
import AdminRoute from './admin/AdminRoute';
import LoginPage from './auth/LoginPage';
import RegisterPage from './auth/RegisterPage';
import RequireAuth from './auth/RequireAuth';

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen flex-col bg-gray-900 text-gray-100">
        <ToastContainer />
        <Routes>
          <Route path="/" element={<Navigate to="/chat/new" replace />} />
          <Route path="/auth/login" element={<LoginPage />} />
          <Route path="/auth/register" element={<RegisterPage />} />
          <Route
            path="/chat/:id"
            element={
              <RequireAuth>
                <ChatPage />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/*"
            element={
              <RequireAuth>
                <AdminRoute>
                  <AdminApp />
                </AdminRoute>
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/chat/new" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
