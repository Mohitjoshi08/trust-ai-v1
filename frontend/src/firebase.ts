import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';

const isDemo = import.meta.env.VITE_DEMO_MODE === 'true';

let auth: any;

if (isDemo) {
  auth = {
    currentUser: {
      getIdToken: async () => 'demo-token',
      uid: 'demo-user',
      email: 'demo@example.com'
    },
    signOut: async () => {},
    onAuthStateChanged: (cb: any) => {
      cb({ uid: 'demo-user', email: 'demo@example.com' });
      return () => {};
    }
  };
} else {
  const firebaseConfig = {
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "dummy",
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "dummy",
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "dummy",
    storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "dummy",
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "dummy",
    appId: import.meta.env.VITE_FIREBASE_APP_ID || "dummy"
  };
  const app = initializeApp(firebaseConfig);
  auth = getAuth(app);
}

export { auth };
