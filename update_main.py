import re
with open('app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r'@bp\.route\(\'/reservation/<int:res_id>/qr\'\).*?return send_file\(img_io, mimetype=\'image/png\'\)'

replacement = '''@bp.route('/reservation/<int:res_id>/qr')
@login_required
def generate_qr(res_id):
    from app.utils import generate_qr_token
    from flask import redirect
    from urllib.parse import quote
    
    reservation = Reservation.query.get_or_404(res_id)
    
    if current_user.id != reservation.user_id and current_user not in reservation.attendees:
        return jsonify({'error': 'Unauthorized'}), 403
        
    token = generate_qr_token(res_id)
    google_qr_url = f"https://chart.googleapis.com/chart?chs=300x300&cht=qr&chl={quote(token)}&choe=UTF-8"
    return redirect(google_qr_url)'''

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open('app/main.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

if new_content != content:
    print('Updated main.py successfully')
else:
    print('No changes made, pattern not found')
