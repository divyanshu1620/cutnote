import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Auth from './pages/Auth';
import Dashboard from './pages/Dashboard';
import ReviewPlayer from './pages/ReviewPlayer';

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Auth />} />
      <Route path="/" element={<Dashboard />} />
      <Route path="/review/:token" element={<ReviewPlayer />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;