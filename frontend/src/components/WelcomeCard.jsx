function WelcomeCard({ userName }) {
  return (
    <div className="welcome-card">
      <div className="welcome-glow" />
      <div className="welcome-content">
        <div className="welcome-text">
          <h1>Welcome back, {userName}</h1>
          <p>Which paper shall we research today?</p>
        </div>
      </div>
    </div>
  );
}

export default WelcomeCard;
