with open('app/templates/base.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find where I injected the custom toast style
idx = content.find('<style>\n            #custom-toast {')
if idx != -1:
    content = content[:idx].strip()

# Append the original starting_soon_meeting script
content += '''

    {% if starting_soon_meeting %}
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            if ('Notification' in window && Notification.permission === 'granted') {
                new Notification("Toplantı Başlıyor!", {
                    body: "'{{ starting_soon_meeting.room.name }}' odasındaki toplantınız başlamak üzere.",
                    icon: "/static/icons/icon-192x192.png"
                });
            } else if ('Notification' in window && Notification.permission !== 'denied') {
                Notification.requestPermission().then(function(permission) {
                    if (permission === 'granted') {
                        new Notification("Toplantı Başlıyor!", {
                            body: "'{{ starting_soon_meeting.room.name }}' odasındaki toplantınız başlamak üzere.",
                            icon: "/static/icons/icon-192x192.png"
                        });
                    }
                });
            }
        });
    </script>
    {% endif %}
</body>
</html>
'''

with open('app/templates/base.html', 'w', encoding='utf-8') as f:
    f.write(content)
