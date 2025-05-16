import React, { useState, useEffect } from 'react';

function App() {
  const [message, setMessage] = useState('Loading...');

  useEffect(() => {
    // Fetch data from the backend API
    fetch('http://localhost:8802/api/v1')
      .then(response => response.json())
      .then(data => {
        setMessage(data.message || 'Connected to GRANTHIK API');
      })
      .catch(error => {
        console.error('Error fetching data:', error);
        setMessage('Failed to connect to API');
      });
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>GRANTHIK Dashboard</h1>
        <p>{message}</p>
      </header>
      <main>
        <p>Welcome to the GRANTHIK platform</p>
      </main>
    </div>
  );
}

export default App;