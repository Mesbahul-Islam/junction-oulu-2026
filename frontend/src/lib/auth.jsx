import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { getMe, login as apiLogin, register as apiRegister, token } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(Boolean(token.get()));

  const refresh = useCallback(async () => {
    if (!token.get()) {
      setMe(null);
      return null;
    }
    try {
      const user = await getMe();
      setMe(user);
      return user;
    } catch {
      token.clear();
      setMe(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = async (email, password) => {
    const { access } = await apiLogin(email, password);
    token.set(access);
    return refresh();
  };

  const register = async (email, username, password) => {
    await apiRegister(email, username, password);
    return login(email, password);
  };

  const logout = () => {
    token.clear();
    setMe(null);
  };

  return (
    <AuthContext.Provider value={{ me, loading, login, register, logout, refresh }}>{children}</AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
