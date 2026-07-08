with open('app/templates/dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

button_html_res = '<button type="button" class="btn" style="width: auto; padding: 0.5rem 1.5rem; font-size: 0.875rem; background: #8b5cf6; margin-right: 0.5rem;" onclick="showQrModal({{ res.id }})">{{ gettext(\'QR Göster\') }}</button>\n                    '

# Add button for reservations (before delete form)
content = content.replace(
    '<form action="{{ url_for(\'main.delete_reservation\', res_id=res.id) }}" method="POST" style="display:inline;">',
    button_html_res + '<form action="{{ url_for(\'main.delete_reservation\', res_id=res.id) }}" method="POST" style="display:inline;">'
)

# Add button for invited_reservations (after add to calendar)
content = content.replace(
    '<a href="{{ res.cal_url }}" target="_blank" class="btn" style="width: auto; padding: 0.5rem 1.5rem; font-size: 0.875rem; background: #3b82f6;">{{ gettext(\'Takvime Ekle\') }}</a>\n                </div>',
    '<a href="{{ res.cal_url }}" target="_blank" class="btn" style="width: auto; padding: 0.5rem 1.5rem; font-size: 0.875rem; background: #3b82f6; margin-right: 0.5rem;">{{ gettext(\'Takvime Ekle\') }}</a>\n                    ' + button_html_res.strip() + '\n                </div>'
)

modal_html = '''
<!-- QR Modal -->
<div id="qrModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 2000; align-items: center; justify-content: center; backdrop-filter: blur(5px);">
    <div style="background: var(--card-bg); padding: 2rem; border-radius: 1rem; border: 1px solid var(--border-color); text-align: center; max-width: 400px; width: 90%;">
        <h3 style="margin-top: 0; margin-bottom: 1.5rem; color: #f8fafc;">{{ gettext('Oda Giriş QR Kodu') }}</h3>
        <p style="font-size: 0.875rem; color: #cbd5e1; margin-bottom: 1.5rem;">{{ gettext('Kapıdaki okuyucuya bu QR kodu okutarak odaya giriş yapabilirsiniz.') }}</p>
        <div style="background: white; padding: 1rem; border-radius: 0.5rem; display: inline-block; margin-bottom: 1.5rem; min-width: 200px; min-height: 200px;">
            <img id="qrImage" src="" alt="QR Kod" style="max-width: 100%; height: auto; display: block;" />
        </div>
        <div>
            <button type="button" class="btn" style="background: #64748b; width: 100%;" onclick="closeQrModal()">{{ gettext('Kapat') }}</button>
        </div>
    </div>
</div>

<script>
function showQrModal(resId) {
    const modal = document.getElementById('qrModal');
    const img = document.getElementById('qrImage');
    img.src = '/reservation/' + resId + '/qr';
    modal.style.display = 'flex';
}
function closeQrModal() {
    document.getElementById('qrModal').style.display = 'none';
}
</script>
'''

content = content.replace('{% endblock %}', modal_html + '\n{% endblock %}')

with open('app/templates/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
