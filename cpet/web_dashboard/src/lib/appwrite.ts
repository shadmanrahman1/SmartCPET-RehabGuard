import { Client, Databases } from 'appwrite';

const client = new Client();

const endpoint = process.env.NEXT_PUBLIC_APPWRITE_ENDPOINT;
const projectId = process.env.NEXT_PUBLIC_APPWRITE_PROJECT_ID;

if (endpoint && projectId) {
  client.setEndpoint(endpoint).setProject(projectId);
} else {
  console.warn('Appwrite configuration is missing from environment variables.');
}

export const databases = new Databases(client);

// Appwrite Config Constants to avoid hardcoding everywhere
export const APPWRITE_CONFIG = {
  databaseId: process.env.NEXT_PUBLIC_APPWRITE_DATABASE_ID || '',
  collections: {
    patients: process.env.NEXT_PUBLIC_APPWRITE_PATIENTS_COLLECTION_ID || '',
  }
};
