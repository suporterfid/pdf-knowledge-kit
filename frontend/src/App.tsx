import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import ChatPage from './ChatPage';
import Login from './Login';
import RequireApiKey from './RequireApiKey';
import AdminApp from './admin/AdminApp';
import AdminRoute from './admin/AdminRoute';

export default function App() {
  return (
    <BrowserRouter>
      <ToastContainer />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireApiKey>
              <ChatPage />
            </RequireApiKey>
          }
        />
        <Route
          path="/admin/*"
          element={
            <RequireApiKey>
              <AdminRoute>
                <AdminApp />
              </AdminRoute>
            </RequireApiKey>
          }
        />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  );
}
