import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import ChatPage from './ChatPage';
import Login from './Login';
import RequireApiKey from './RequireApiKey';
import AdminApp from './admin/AdminApp';

export default function App() {
  return (
    <BrowserRouter>
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
              <AdminApp />
            </RequireApiKey>
          }
        />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  );
}
