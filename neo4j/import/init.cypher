// Create sample data and constraints
CREATE CONSTRAINT user_email IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE;
CREATE CONSTRAINT session_token IF NOT EXISTS FOR (s:Session) REQUIRE s.token IS UNIQUE;

// Create sample nodes
CREATE (u1:User {name: 'John Doe', email: 'john@example.com', created_at: datetime()})
CREATE (u2:User {name: 'Jane Smith', email: 'jane@example.com', created_at: datetime()})

// Create relationships
CREATE (u1)-[:FRIEND_WITH {since: date()}]->(u2);

// Create indexes
CREATE INDEX user_email_idx IF NOT EXISTS FOR (u:User) ON (u.email);
CREATE INDEX user_name_idx IF NOT EXISTS FOR (u:User) ON (u.name);