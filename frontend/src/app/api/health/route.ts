import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const checks = [];

  // Backend API check
  try {
    const backendResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/health`);
    checks.push({
      service: 'backend',
      status: backendResponse.ok ? 'healthy' : 'unhealthy'
    });
  } catch (error) {
    checks.push({
      service: 'backend',
      status: 'unhealthy',
      error: 'Connection failed'
    });
  }

  const allHealthy = checks.every(check => check.status === 'healthy');
  
  return NextResponse.json({
    status: allHealthy ? 'healthy' : 'unhealthy',
    checks
  }, {
    status: allHealthy ? 200 : 503
  });
}