# Kyro — Chrome extension

Кнопка **«В Kyro»** на YouTube + пункт контекстного меню «Сохранить в Kyro».

## Установка (распакованное)

1. Откройте `chrome://extensions`
2. Включите «Режим разработчика»
3. «Загрузить распакованное расширение» → папка `extension/` этого репозитория
4. Откройте popup расширения, вставьте токен сессии:
   - зайдите в [Kyro](https://clip-queue-web-production.up.railway.app)
   - DevTools → Console: `localStorage.getItem('cq_session_token')`
5. На странице ролика YouTube нажмите **В Kyro**

Токен — ваш bearer к API; не публикуйте его.
